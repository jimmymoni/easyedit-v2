"""
End-to-End Workflow Test
Tests the complete video processing pipeline:
1. Upload video to S3 (chunked upload)
2. Extract audio with Replicate
3. Transcribe with Whisper
4. Generate DRT XML
5. Download result

This test requires a local video file for testing.
Usage: python test_end_to_end_workflow.py <path_to_video>
"""
import sys
import os
import time
import requests
from pathlib import Path

# Test configuration
BACKEND_URL = "http://localhost:5000"

def print_section(title):
    """Print section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")

def check_test_video(video_path_arg):
    """Check test video exists"""
    print_section("STEP 1: Validate Test Video")

    video_path = Path(video_path_arg)

    if not video_path.exists():
        print(f"[ERROR] Video file not found: {video_path}")
        print(f"Please provide a valid video file path")
        sys.exit(1)

    file_size = video_path.stat().st_size
    print(f"[OK] Test video: {video_path}")
    print(f"[OK] File size: {file_size:,} bytes")

    return video_path, file_size

def get_demo_token():
    """Get JWT token for API authentication"""
    print_section("STEP 2: Get Authentication Token")

    response = requests.get(f"{BACKEND_URL}/auth/demo-token")
    response.raise_for_status()

    data = response.json()
    token = data["access_token"]

    print(f"[OK] Token: {token[:30]}...")
    return token

def init_upload(token, filename, file_size):
    """Initialize chunked upload"""
    print_section("STEP 3: Initialize Upload")

    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "filename": filename,
        "file_size": file_size
    }

    response = requests.post(
        f"{BACKEND_URL}/upload/init",
        headers=headers,
        json=payload
    )
    response.raise_for_status()

    data = response.json()

    if not data.get("success"):
        raise Exception(f"Upload init failed: {data}")

    job_id = data["job_id"]
    upload_session = data["upload_session"]
    chunk_urls = upload_session["chunk_urls"]

    print(f"[OK] Job ID: {job_id}")
    print(f"[OK] Chunk URLs: {len(chunk_urls)} URLs generated")
    print(f"[OK] Total chunks: {upload_session['total_chunks']}")

    return job_id, chunk_urls

def upload_chunks(token, job_id, chunk_urls, file_path):
    """Upload video chunks to S3"""
    print_section("STEP 4: Upload Video Chunks")

    headers = {"Authorization": f"Bearer {token}"}

    with open(file_path, "rb") as f:
        for chunk_url in chunk_urls:
            part_number = chunk_url["part_number"]
            upload_url = chunk_url["upload_url"]
            chunk_size = chunk_url["size"]

            chunk_data = f.read(chunk_size)

            if not chunk_data:
                break

            print(f"Uploading chunk {part_number}/{len(chunk_urls)} ({len(chunk_data):,} bytes)...")

            # Upload to S3
            response = requests.put(upload_url, data=chunk_data)
            response.raise_for_status()

            etag = response.headers["ETag"].strip('"')

            # Notify backend
            notify_payload = {
                "job_id": job_id,
                "part_number": part_number,
                "etag": etag
            }

            response = requests.post(
                f"{BACKEND_URL}/upload/chunk-complete",
                headers=headers,
                json=notify_payload
            )
            response.raise_for_status()

            data = response.json()
            progress = data.get("progress", {}).get("progress", 0) * 100
            print(f"  [OK] Chunk {part_number} uploaded (ETag: {etag[:12]}...) - {progress:.1f}% complete")

    print(f"\n[OK] All chunks uploaded successfully")

def complete_upload(token, job_id):
    """Finalize upload and trigger processing"""
    print_section("STEP 5: Complete Upload & Trigger Processing")

    headers = {"Authorization": f"Bearer {token}"}
    payload = {"job_id": job_id}

    response = requests.post(
        f"{BACKEND_URL}/upload/complete",
        headers=headers,
        json=payload
    )
    response.raise_for_status()

    data = response.json()
    print(f"[OK] Upload completed")
    print(f"[OK] Video URL: {data.get('video_url', 'N/A')}")
    print(f"[OK] Status: {data.get('status', 'N/A')}")

def monitor_processing(token, job_id):
    """Monitor processing progress"""
    print_section("STEP 6: Monitor Processing Progress")

    headers = {"Authorization": f"Bearer {token}"}

    print("Monitoring job status (polling every 5 seconds)...\n")

    while True:
        response = requests.get(
            f"{BACKEND_URL}/video-status/{job_id}",
            headers=headers
        )
        response.raise_for_status()

        data = response.json()
        status = data.get("status", "unknown")
        progress = data.get("progress", 0)
        current_stage = data.get("current_stage", "N/A")

        print(f"[{time.strftime('%H:%M:%S')}] Status: {status} | Progress: {progress}% | Stage: {current_stage}")

        if status == "completed":
            print("\n[OK] Processing completed successfully!")
            return data
        elif status == "failed":
            error = data.get("error", "Unknown error")
            print(f"\n[ERROR] Processing failed: {error}")
            sys.exit(1)

        time.sleep(5)

def download_result(token, job_id):
    """Download the generated DRT XML file"""
    print_section("STEP 7: Download Result (DRT XML)")

    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(
        f"{BACKEND_URL}/download/{job_id}",
        headers=headers
    )
    response.raise_for_status()

    output_path = Path(f"test_result_{job_id}.drt")

    with open(output_path, "wb") as f:
        f.write(response.content)

    file_size = output_path.stat().st_size

    print(f"[OK] Downloaded DRT XML: {output_path}")
    print(f"[OK] File size: {file_size:,} bytes")

    # Verify XML structure
    with open(output_path, "r", encoding="utf-8") as f:
        xml_content = f.read()

        if "<xmeml version=" in xml_content:
            print("[OK] Valid DaVinci Resolve XML structure detected")
        else:
            print("[WARN]  Warning: XML structure may be invalid")

    return output_path

def main():
    """Run end-to-end workflow test"""
    print("\n" + "=" * 70)
    print("  END-TO-END WORKFLOW TEST")
    print("  Upload -> Audio -> Whisper -> XML")
    print("=" * 70)

    # Check command line arguments
    if len(sys.argv) < 2:
        print("\n[ERROR] Usage: python test_end_to_end_workflow.py <path_to_video>")
        print("Example: python test_end_to_end_workflow.py test.mp4\n")
        sys.exit(1)

    try:
        # Step 1: Validate test video
        video_path, file_size = check_test_video(sys.argv[1])

        # Step 2: Get auth token
        token = get_demo_token()

        # Step 3: Initialize upload
        job_id, chunk_urls = init_upload(token, video_path.name, file_size)

        # Step 4: Upload chunks
        upload_chunks(token, job_id, chunk_urls, video_path)

        # Step 5: Complete upload (triggers processing)
        complete_upload(token, job_id)

        # Step 6: Monitor processing
        result = monitor_processing(token, job_id)

        # Step 7: Download result
        output_path = download_result(token, job_id)

        # Final summary
        print_section("TEST COMPLETE")
        print(f"[OK] Job ID: {job_id}")
        print(f"[OK] Input: {video_path} ({file_size:,} bytes)")
        print(f"[OK] Output: {output_path}")
        print(f"[OK] Workflow: Upload -> Audio -> Whisper -> XML")
        print(f"\nAll steps completed successfully!\n")

    except requests.exceptions.ConnectionError:
        print("\n[ERROR] ERROR: Cannot connect to backend at", BACKEND_URL)
        print("   Make sure the Flask server is running:")
        print("   cd backend && python app.py\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
