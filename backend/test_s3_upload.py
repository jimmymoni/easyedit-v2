import requests
import os

BASE_URL = "http://localhost:5000"
TOKEN = None

def get_token():
    global TOKEN
    response = requests.get(f"{BASE_URL}/auth/demo-token")
    TOKEN = response.json()["access_token"]
    print(f"[OK] Got auth token: {TOKEN[:20]}...")

def init_upload():
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }

    test_file = "test_video.mp4"
    with open(test_file, "wb") as f:
        f.write(b"0" * 10485760)  # 10MB

    file_size = os.path.getsize(test_file)

    response = requests.post(
        f"{BASE_URL}/upload/init",
        json={"filename": test_file, "file_size": file_size},
        headers=headers
    )

    data = response.json()
    if data.get("success"):
        print(f"[OK] Upload initialized: {data['job_id']}")
        print(f"  Total chunks: {data['upload_session']['total_chunks']}")
        return data["job_id"], data["upload_session"], test_file
    else:
        print(f"[FAIL] Failed: {data}")
        return None, None, None

def upload_chunk(chunk_url, chunk_data):
    response = requests.put(
        chunk_url["upload_url"],
        data=chunk_data
    )
    if response.status_code == 200:
        etag = response.headers.get("ETag").strip('"')
        print(f"[OK] Chunk {chunk_url['part_number']} uploaded (ETag: {etag[:10]}...)")
        return etag
    else:
        print(f"[FAIL] Chunk {chunk_url['part_number']} failed: {response.status_code}")
        print(f"  Response: {response.text}")
        return None

def notify_chunk_complete(job_id, part_number, etag):
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        f"{BASE_URL}/upload/chunk-complete",
        json={"job_id": job_id, "part_number": part_number, "etag": etag},
        headers=headers
    )

    data = response.json()
    if data.get("success"):
        progress = data["progress"]["progress"] * 100
        print(f"  Backend notified: {progress:.1f}% complete")
        return True
    return False

def complete_upload(job_id):
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        f"{BASE_URL}/upload/complete",
        json={"job_id": job_id},
        headers=headers
    )

    data = response.json()
    if data.get("success"):
        print(f"[OK] Upload complete! Message: {data.get('message')}")
        return True
    else:
        print(f"[FAIL] Failed to complete: {data}")
        return False

def test_full_flow():
    print("\n*** Testing S3 Chunked Upload Flow ***\n")
    print("=" * 50)

    print("\n[1/4] Getting auth token...")
    get_token()

    print("\n[2/4] Initializing upload...")
    job_id, upload_session, test_file = init_upload()
    if not job_id:
        print("\n[X] Test failed at initialization\n")
        return

    print(f"\n[3/4] Uploading {len(upload_session['chunk_urls'])} chunks...")
    with open(test_file, "rb") as f:
        for chunk_url in upload_session["chunk_urls"]:
            chunk_data = f.read(chunk_url["size"])
            etag = upload_chunk(chunk_url, chunk_data)
            if not etag:
                print("\n[X] Test failed during chunk upload\n")
                return
            notify_chunk_complete(job_id, chunk_url["part_number"], etag)

    print("\n[4/4] Finalizing upload...")
    if complete_upload(job_id):
        print("\n" + "=" * 50)
        print("[SUCCESS] ALL TESTS PASSED! S3 upload system is working!")
        print("=" * 50 + "\n")

    os.remove(test_file)
    print("Cleaned up test file\n")

if __name__ == "__main__":
    test_full_flow()
