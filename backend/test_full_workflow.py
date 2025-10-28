"""
Quick test script for full easyedit-v2 workflow
Tests: Upload → Process → Download with transcription
"""

import requests
import time
import json
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:5000"
AUDIO_FILE = r"C:\Users\Tomso\Downloads\Timeline 1 audio (1).wav"

# Demo token for testing
DEMO_TOKEN = "demo-token-12345"

def get_auth_token():
    """Get authentication token"""
    print("1. Getting authentication token...")
    response = requests.get(f"{BASE_URL}/auth/demo-token")

    if response.status_code == 200:
        data = response.json()
        token = data['access_token']
        print(f"   [OK] Token obtained: {token[:20]}...")
        return token
    else:
        print(f"   [X] Failed to get token: {response.status_code}")
        print(f"   Response: {response.text}")
        return None

def upload_files(token, audio_path):
    """Upload audio file with dummy DRT"""
    print("\n2. Uploading audio file...")

    headers = {"Authorization": f"Bearer {token}"}

    # Create a minimal dummy DRT file for testing (just need valid XML structure)
    dummy_drt = """<?xml version="1.0" encoding="UTF-8"?>
<xmeml version="5">
  <sequence>
    <name>Dummy Timeline</name>
    <duration>100</duration>
    <rate>
      <timebase>25</timebase>
    </rate>
    <media>
      <audio></audio>
    </media>
  </sequence>
</xmeml>"""

    with open(audio_path, 'rb') as audio_file:
        files = {
            'audio': ('audio.wav', audio_file, 'audio/wav'),
            'drt': ('timeline.drt', dummy_drt.encode('utf-8'), 'application/xml')
        }

        response = requests.post(
            f"{BASE_URL}/upload",
            headers=headers,
            files=files
        )

    if response.status_code == 200:
        data = response.json()
        job_id = data['job_id']
        print(f"   [OK] Upload successful!")
        print(f"   Job ID: {job_id}")
        return job_id
    else:
        print(f"   [X] Upload failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return None

def start_processing(token, job_id):
    """Start processing with transcription enabled"""
    print("\n3. Starting processing with transcription...")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "enable_transcription": True,
        "enable_speaker_diarization": True,
        "enable_ai_enhancement": False,  # Set to True if you want AI enhancements
        "detect_filler_words": False,
        "remove_silence": True,
        "silence_threshold_db": -40
    }

    response = requests.post(
        f"{BASE_URL}/process/{job_id}",
        headers=headers,
        json=payload
    )

    if response.status_code == 200:
        print(f"   [OK] Processing started!")
        return True
    else:
        print(f"   [X] Processing failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return False

def check_status(token, job_id):
    """Check processing status"""
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(
        f"{BASE_URL}/status/{job_id}",
        headers=headers
    )

    if response.status_code == 200:
        return response.json()
    else:
        print(f"   [X] Status check failed: {response.status_code}")
        return None

def wait_for_completion(token, job_id, max_wait=600):
    """Wait for processing to complete"""
    print("\n4. Waiting for processing to complete...")
    print("   (This will take 30-120 seconds for transcription)")

    start_time = time.time()
    last_status = None

    while time.time() - start_time < max_wait:
        status_data = check_status(token, job_id)

        if not status_data:
            break

        current_status = status_data.get('status')
        progress = status_data.get('progress', 0)

        if current_status != last_status:
            print(f"\n   Status: {current_status} ({progress:.0f}%)")
            last_status = current_status

        if current_status == 'completed':
            print(f"   [OK] Processing completed in {time.time() - start_time:.1f}s")
            return status_data
        elif current_status == 'failed':
            print(f"   [X] Processing failed!")
            print(f"   Error: {status_data.get('error', 'Unknown error')}")
            return None

        # Show progress for long-running tasks
        if progress > 0:
            print(f"   Progress: {progress:.0f}%", end='\r')

        time.sleep(2)  # Poll every 2 seconds

    print(f"   [X] Timeout after {max_wait}s")
    return None

def get_transcription(token, job_id):
    """Get transcription data for a job"""
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(
        f"{BASE_URL}/transcription/{job_id}",
        headers=headers
    )

    if response.status_code == 200:
        return response.json()
    else:
        return None

def show_results(token, job_id, status_data):
    """Display processing results"""
    print("\n" + "="*60)
    print("PROCESSING RESULTS")
    print("="*60)

    # Check if transcription is available
    if status_data.get('transcription_available'):
        print("\nFetching transcription data...")
        trans_data = get_transcription(token, job_id)

        if trans_data and 'transcription' in trans_data:
            trans = trans_data['transcription']
            print(f"\n[TRANSCRIPT] TRANSCRIPTION:")
            print(f"   Provider: {trans.get('provider', 'N/A')}")
            print(f"   Word count: {trans.get('word_count', 0)}")
            print(f"   Duration: {trans.get('duration', 0):.1f}s")
            print(f"   Speakers: {len(trans.get('speakers', []))}")
            print(f"   Confidence: {trans.get('confidence', 0):.1%}")

            if trans.get('transcript'):
                print(f"\n   Transcript preview (first 300 chars):")
                print(f"   {'-'*56}")
                print(f"   {trans['transcript'][:300]}...")
                print(f"   {'-'*56}")
        else:
            print("\n   [X] Could not fetch transcription data")

    # Audio analysis results
    if 'audio_analysis' in status_data:
        audio = status_data['audio_analysis']
        print(f"\n[AUDIO] AUDIO ANALYSIS:")
        print(f"   Duration: {audio.get('duration', 0):.1f}s")
        print(f"   Sample rate: {audio.get('sample_rate', 0)} Hz")
        print(f"   Silence detected: {len(audio.get('silence_segments', []))} segments")
        print(f"   Speech segments: {len(audio.get('speech_segments', []))} segments")

    # Timeline results
    print(f"\n[TIMELINE] TIMELINE EDITING:")
    print(f"   Status: {status_data.get('status', 'N/A')}")
    print(f"   Progress: {status_data.get('progress', 0):.0f}%")

    print("\n" + "="*60)

def download_result(token, job_id):
    """Download processed DRT file"""
    print("\n5. Downloading processed file...")

    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(
        f"{BASE_URL}/download/{job_id}",
        headers=headers
    )

    if response.status_code == 200:
        output_file = f"processed_{job_id}.drt"
        with open(output_file, 'wb') as f:
            f.write(response.content)
        print(f"   [OK] Downloaded: {output_file}")
        print(f"   Size: {len(response.content)} bytes")
        return output_file
    else:
        print(f"   [X] Download failed: {response.status_code}")
        return None

def main():
    print("="*60)
    print("EasyEdit v2 - Full Workflow Test")
    print("Testing: Upload -> Transcribe -> Process -> Download")
    print("="*60)

    # Check if audio file exists
    if not Path(AUDIO_FILE).exists():
        print(f"\nX Audio file not found: {AUDIO_FILE}")
        print("Please update AUDIO_FILE path in the script")
        return

    print(f"\nAudio file: {AUDIO_FILE}")
    print(f"File size: {Path(AUDIO_FILE).stat().st_size / (1024*1024):.2f}MB")

    # Step 1: Get auth token
    token = get_auth_token()
    if not token:
        return

    # Step 2: Upload files
    job_id = upload_files(token, AUDIO_FILE)
    if not job_id:
        return

    # Step 3: Start processing
    if not start_processing(token, job_id):
        return

    # Step 4: Wait for completion
    result = wait_for_completion(token, job_id, max_wait=300)
    if not result:
        return

    # Step 5: Show results
    show_results(token, job_id, result)

    # Step 6: Download (optional - only if DRT was provided)
    # download_result(token, job_id)

    print("\n[OK] Test completed successfully!")
    print(f"\nYou can view detailed results at: {BASE_URL}/status/{job_id}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
