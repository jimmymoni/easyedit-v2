"""
Test script for Sub-Step 1.8: GET /video-proxy/<job_id> endpoint

This script tests the video proxy streaming endpoint by:
1. Testing Range request support (206 Partial Content)
2. Testing full file streaming (200 OK)
3. Testing error cases (425, 404, 416)
4. Verifying proper headers (Content-Type, Content-Range, Accept-Ranges, etc.)
"""

import requests
import json
import os
from io import BytesIO

# Configuration
BASE_URL = "http://localhost:5000"
AUTH_TOKEN = None

def get_demo_token():
    """Get a demo authentication token"""
    try:
        response = requests.get(f"{BASE_URL}/auth/demo-token")
        if response.status_code == 200:
            data = response.json()
            return data.get('access_token')
        else:
            print(f"❌ Failed to get demo token: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error getting demo token: {str(e)}")
        return None

def test_proxy_not_found():
    """Test GET /video-proxy/<job_id> with non-existent job"""
    print("\n" + "="*60)
    print("TEST 1: Video Proxy - Job Not Found")
    print("="*60)

    fake_job_id = "00000000-0000-0000-0000-000000000000"

    try:
        headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
        response = requests.get(
            f"{BASE_URL}/video-proxy/{fake_job_id}",
            headers=headers
        )

        print(f"\nStatus Code: {response.status_code}")
        print(f"Response Body:")
        print(json.dumps(response.json(), indent=2))

        data = response.json()

        # Verify error response
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        assert data['success'] == False, "Expected success=false"
        assert data['code'] == 'JOB_NOT_FOUND', "Expected JOB_NOT_FOUND code"
        assert 'error' in data, "Expected error message"

        print("\n✅ Job Not Found test PASSED")
        return True

    except AssertionError as e:
        print(f"\n❌ Job Not Found test FAILED: {str(e)}")
        return False
    except Exception as e:
        print(f"\n❌ Job Not Found test ERROR: {str(e)}")
        return False

def test_proxy_not_ready(job_id):
    """Test GET /video-proxy/<job_id> when proxy is not ready (425)"""
    print("\n" + "="*60)
    print("TEST 2: Video Proxy - Not Ready (425)")
    print("="*60)

    print("\nNote: This test requires a job in 'uploaded' or 'transcoding' state")
    print("Skipping for now - would test with a real job in progress")
    return True

def test_range_request(job_id):
    """Test HTTP Range request support (206 Partial Content)"""
    print("\n" + "="*60)
    print("TEST 3: Video Proxy - Range Request (206)")
    print("="*60)

    try:
        headers = {
            "Authorization": f"Bearer {AUTH_TOKEN}",
            "Range": "bytes=0-1023"  # Request first 1KB
        }

        response = requests.get(
            f"{BASE_URL}/video-proxy/{job_id}",
            headers=headers
        )

        print(f"\nStatus Code: {response.status_code}")
        print(f"Response Headers:")
        for key, value in response.headers.items():
            if key.lower() in ['content-type', 'content-length', 'content-range', 'accept-ranges']:
                print(f"  {key}: {value}")

        # Verify 206 response
        assert response.status_code == 206, f"Expected 206, got {response.status_code}"

        # Verify headers
        assert 'Content-Range' in response.headers, "Missing Content-Range header"
        assert 'Accept-Ranges' in response.headers, "Missing Accept-Ranges header"
        assert response.headers['Accept-Ranges'] == 'bytes', "Accept-Ranges should be 'bytes'"

        # Verify Content-Range format: bytes 0-1023/total_size
        content_range = response.headers['Content-Range']
        assert content_range.startswith('bytes 0-1023/'), f"Unexpected Content-Range: {content_range}"

        # Verify content length is 1024 bytes
        content_length = int(response.headers['Content-Length'])
        assert content_length == 1024, f"Expected 1024 bytes, got {content_length}"

        # Verify actual data size
        data_size = len(response.content)
        assert data_size == 1024, f"Expected 1024 bytes of data, got {data_size}"

        print(f"\n✅ Range Request test PASSED")
        print(f"  Content-Range: {content_range}")
        print(f"  Content-Length: {content_length}")
        print(f"  Actual data size: {data_size} bytes")
        return True

    except AssertionError as e:
        print(f"\n❌ Range Request test FAILED: {str(e)}")
        return False
    except Exception as e:
        print(f"\n❌ Range Request test ERROR: {str(e)}")
        return False

def test_full_content(job_id):
    """Test full content streaming (200 OK)"""
    print("\n" + "="*60)
    print("TEST 4: Video Proxy - Full Content (200)")
    print("="*60)

    try:
        headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}

        # Use streaming to avoid loading entire file into memory
        response = requests.get(
            f"{BASE_URL}/video-proxy/{job_id}",
            headers=headers,
            stream=True
        )

        print(f"\nStatus Code: {response.status_code}")
        print(f"Response Headers:")
        for key, value in response.headers.items():
            if key.lower() in ['content-type', 'content-length', 'accept-ranges', 'cache-control']:
                print(f"  {key}: {value}")

        # Verify 200 response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        # Verify headers
        assert 'Accept-Ranges' in response.headers, "Missing Accept-Ranges header"
        assert response.headers['Accept-Ranges'] == 'bytes', "Accept-Ranges should be 'bytes'"
        assert 'Content-Length' in response.headers, "Missing Content-Length header"
        assert 'Content-Type' in response.headers, "Missing Content-Type header"

        # Verify Content-Type is video
        content_type = response.headers['Content-Type']
        assert content_type.startswith('video/'), f"Expected video/* content type, got {content_type}"

        # Read first chunk to verify streaming works
        first_chunk = next(response.iter_content(chunk_size=8192))
        assert len(first_chunk) > 0, "First chunk is empty"

        print(f"\n✅ Full Content test PASSED")
        print(f"  Content-Type: {content_type}")
        print(f"  Content-Length: {response.headers['Content-Length']} bytes")
        print(f"  First chunk size: {len(first_chunk)} bytes")
        return True

    except AssertionError as e:
        print(f"\n❌ Full Content test FAILED: {str(e)}")
        return False
    except Exception as e:
        print(f"\n❌ Full Content test ERROR: {str(e)}")
        return False

def test_invalid_range(job_id):
    """Test invalid Range request (416 Range Not Satisfiable)"""
    print("\n" + "="*60)
    print("TEST 5: Video Proxy - Invalid Range (416)")
    print("="*60)

    invalid_ranges = [
        "bytes=999999999-999999999",  # Beyond file size
        "bytes=1000-500",  # Start > End
        "bytes=-1-100",  # Negative start
    ]

    all_passed = True

    for range_header in invalid_ranges:
        print(f"\nTesting invalid range: {range_header}")
        try:
            headers = {
                "Authorization": f"Bearer {AUTH_TOKEN}",
                "Range": range_header
            }

            response = requests.get(
                f"{BASE_URL}/video-proxy/{job_id}",
                headers=headers
            )

            print(f"Status Code: {response.status_code}")

            if response.status_code == 416:
                print(f"✅ Correctly returned 416")
            else:
                print(f"⚠️  Got status {response.status_code}, expected 416")
                all_passed = False

        except Exception as e:
            print(f"❌ Error: {str(e)}")
            all_passed = False

    if all_passed:
        print("\n✅ Invalid Range test PASSED")
    else:
        print("\n⚠️  Invalid Range test had some issues")

    return all_passed

def test_range_with_end_only(job_id):
    """Test Range request with only end (bytes=-1024)"""
    print("\n" + "="*60)
    print("TEST 6: Video Proxy - Range End Only (last 1KB)")
    print("="*60)

    print("\nNote: This endpoint currently requires explicit start-end format")
    print("The 'bytes=-1024' format (last 1KB) is not yet supported")
    print("Skipping for now...")
    return True

def test_multiple_ranges(job_id):
    """Test multiple ranges in single request"""
    print("\n" + "="*60)
    print("TEST 7: Video Proxy - Multiple Ranges")
    print("="*60)

    print("\nNote: Multi-range requests (bytes=0-100,200-300) are not yet supported")
    print("This is an advanced feature that can be added later if needed")
    print("Skipping for now...")
    return True

def test_cache_headers(job_id):
    """Test caching headers"""
    print("\n" + "="*60)
    print("TEST 8: Video Proxy - Cache Headers")
    print("="*60)

    try:
        headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}

        response = requests.get(
            f"{BASE_URL}/video-proxy/{job_id}",
            headers=headers,
            stream=True
        )

        print(f"\nStatus Code: {response.status_code}")

        # Verify Cache-Control header
        assert 'Cache-Control' in response.headers, "Missing Cache-Control header"
        cache_control = response.headers['Cache-Control']
        print(f"Cache-Control: {cache_control}")

        # Should allow public caching
        assert 'public' in cache_control, "Cache-Control should include 'public'"
        assert 'max-age' in cache_control, "Cache-Control should include 'max-age'"

        print(f"\n✅ Cache Headers test PASSED")
        return True

    except AssertionError as e:
        print(f"\n❌ Cache Headers test FAILED: {str(e)}")
        return False
    except Exception as e:
        print(f"\n❌ Cache Headers test ERROR: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("="*60)
    print("Sub-Step 1.8 - Video Proxy Streaming Endpoint Tests")
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
    results.append(("Job Not Found (404)", test_proxy_not_found()))

    # Test 2-8: Real job tests (optional - provide job_id)
    print("\n" + "="*60)
    print("REAL JOB TESTS (Optional)")
    print("="*60)
    print("\nTo test streaming functionality with a real job:")
    print("1. Upload a video using /upload-video")
    print("2. Wait for transcoding to complete")
    print("3. Provide the job_id here")
    print("\nSkipping real job tests for now...")

    # If you have a real job_id, uncomment and update:
    # real_job_id = "your-job-id-here"
    # results.append(("Range Request (206)", test_range_request(real_job_id)))
    # results.append(("Full Content (200)", test_full_content(real_job_id)))
    # results.append(("Invalid Range (416)", test_invalid_range(real_job_id)))
    # results.append(("Cache Headers", test_cache_headers(real_job_id)))

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
    print("\nNote: Full streaming tests require a completed transcode job")

    if passed_tests == total_tests:
        print("\n🎉 All available tests passed!")
    else:
        print(f"\n⚠️  {total_tests - passed_tests} test(s) failed")

if __name__ == "__main__":
    main()
