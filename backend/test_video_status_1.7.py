"""
Test script for Sub-Step 1.7: GET /video-status/<job_id> endpoint

This script tests the video status endpoint by:
1. Creating a mock VideoJob in memory
2. Making GET requests to /video-status/<job_id>
3. Verifying the response structure
4. Testing error cases (job not found, invalid job_id)
"""

import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:5000"
AUTH_TOKEN = None  # Will be fetched from /auth/demo-token

def get_demo_token():
    """Get a demo authentication token"""
    try:
        response = requests.get(f"{BASE_URL}/auth/demo-token")
        if response.status_code == 200:
            data = response.json()
            return data.get('access_token')
        else:
            print(f"❌ Failed to get demo token: {response.status_code}")
            print(f"Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error getting demo token: {str(e)}")
        return None

def create_mock_job_in_memory():
    """
    Create a mock VideoJob directly in the app's memory.
    This simulates a job that was created by the upload-video endpoint.

    Since we can't directly inject into the running app's memory without
    actually uploading a video, we'll upload a real video file in a separate test.

    For now, we'll test with a known job_id from a previous upload or create one.
    """
    print("\nNote: This test requires either:")
    print("1. A job_id from a previous /upload-video call")
    print("2. Or we can test the 'job not found' case with a fake ID")
    return None

def test_video_status_not_found():
    """Test GET /video-status/<job_id> with non-existent job"""
    print("\n" + "="*60)
    print("TEST 1: Video Status - Job Not Found")
    print("="*60)

    fake_job_id = "00000000-0000-0000-0000-000000000000"

    try:
        headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
        response = requests.get(
            f"{BASE_URL}/video-status/{fake_job_id}",
            headers=headers
        )

        print(f"\nStatus Code: {response.status_code}")
        print(f"Response Body:")
        print(json.dumps(response.json(), indent=2))

        data = response.json()

        # Verify error response structure
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        assert data['success'] == False, "Expected success=false"
        assert data['code'] == 'JOB_NOT_FOUND', "Expected JOB_NOT_FOUND code"
        assert 'error' in data, "Expected error message"
        assert data['job_id'] == fake_job_id, "Expected job_id in response"

        print("\n✅ Job Not Found test PASSED")
        return True

    except AssertionError as e:
        print(f"\n❌ Job Not Found test FAILED: {str(e)}")
        return False
    except Exception as e:
        print(f"\n❌ Job Not Found test ERROR: {str(e)}")
        return False

def test_video_status_invalid_job_id():
    """Test GET /video-status/<job_id> with invalid job_id format"""
    print("\n" + "="*60)
    print("TEST 2: Video Status - Invalid Job ID")
    print("="*60)

    invalid_job_ids = [
        "invalid/job/id",  # Contains slashes
        "../../etc/passwd",  # Path traversal attempt
        "job id with spaces",  # Contains spaces
        "job-id-with-<script>",  # Contains HTML
    ]

    all_passed = True

    for invalid_id in invalid_job_ids:
        print(f"\nTesting invalid job_id: {invalid_id}")
        try:
            headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
            response = requests.get(
                f"{BASE_URL}/video-status/{invalid_id}",
                headers=headers
            )

            print(f"Status Code: {response.status_code}")

            # Should return 400 Bad Request for invalid format
            if response.status_code == 400:
                data = response.json()
                print(f"✅ Correctly rejected: {data.get('error', 'Unknown error')}")
            else:
                print(f"⚠️  Got status {response.status_code}, expected 400")
                all_passed = False

        except Exception as e:
            print(f"❌ Error: {str(e)}")
            all_passed = False

    if all_passed:
        print("\n✅ Invalid Job ID test PASSED")
    else:
        print("\n⚠️  Invalid Job ID test had some issues")

    return all_passed

def test_video_status_with_real_job(job_id):
    """Test GET /video-status/<job_id> with a real job from upload"""
    print("\n" + "="*60)
    print("TEST 3: Video Status - Real Job")
    print("="*60)

    try:
        headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
        response = requests.get(
            f"{BASE_URL}/video-status/{job_id}",
            headers=headers
        )

        print(f"\nStatus Code: {response.status_code}")
        print(f"Response Body:")
        print(json.dumps(response.json(), indent=2))

        data = response.json()

        # Verify successful response structure
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert data['success'] == True, "Expected success=true"
        assert data['job_id'] == job_id, "Expected matching job_id"

        # Verify required fields
        required_fields = [
            'status', 'original_metadata', 'transcode_progress',
            'transcode_progress_percent', 'proxy_ready',
            'created_at', 'updated_at'
        ]

        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Verify original_metadata structure
        metadata_fields = [
            'filename', 'size_bytes', 'size_mb', 'format',
            'duration_seconds', 'resolution', 'width', 'height',
            'fps', 'codec', 'bitrate', 'has_audio'
        ]

        for field in metadata_fields:
            assert field in data['original_metadata'], f"Missing metadata field: {field}"

        # Verify data types
        assert isinstance(data['transcode_progress'], (int, float)), "transcode_progress should be numeric"
        assert isinstance(data['transcode_progress_percent'], int), "transcode_progress_percent should be int"
        assert isinstance(data['proxy_ready'], bool), "proxy_ready should be boolean"

        # Verify status is valid
        valid_statuses = ['uploading', 'uploaded', 'transcoding', 'ready', 'failed', 'cancelled']
        assert data['status'] in valid_statuses, f"Invalid status: {data['status']}"

        print("\n✅ Real Job test PASSED")
        print(f"\nJob Details:")
        print(f"  Status: {data['status']}")
        print(f"  Filename: {data['original_metadata']['filename']}")
        print(f"  Duration: {data['original_metadata']['duration_seconds']}s")
        print(f"  Resolution: {data['original_metadata']['resolution']}")
        print(f"  Progress: {data['transcode_progress_percent']}%")
        print(f"  Proxy Ready: {data['proxy_ready']}")

        return True

    except AssertionError as e:
        print(f"\n❌ Real Job test FAILED: {str(e)}")
        return False
    except Exception as e:
        print(f"\n❌ Real Job test ERROR: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("="*60)
    print("Sub-Step 1.7 - Video Status Endpoint Tests")
    print("="*60)

    # Step 1: Get authentication token
    print("\nGetting authentication token...")
    global AUTH_TOKEN
    AUTH_TOKEN = get_demo_token()

    if not AUTH_TOKEN:
        print("❌ Cannot proceed without authentication token")
        return

    print(f"✅ Got auth token: {AUTH_TOKEN[:20]}...")

    # Step 2: Run tests
    results = []

    # Test 1: Job not found
    results.append(("Job Not Found", test_video_status_not_found()))

    # Test 2: Invalid job ID format
    results.append(("Invalid Job ID", test_video_status_invalid_job_id()))

    # Test 3: Real job (optional - provide job_id from previous upload)
    print("\n" + "="*60)
    print("TEST 3: Real Job Status (Optional)")
    print("="*60)
    print("\nTo test with a real job, either:")
    print("1. Upload a video using the /upload-video endpoint first")
    print("2. Provide a job_id from a previous upload")
    print("\nSkipping real job test for now...")

    # Step 3: Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")

    total_tests = len(results)
    passed_tests = sum(1 for _, passed in results if passed)

    print(f"\nTotal: {passed_tests}/{total_tests} tests passed")

    if passed_tests == total_tests:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {total_tests - passed_tests} test(s) failed")

if __name__ == "__main__":
    main()
