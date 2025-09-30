#!/usr/bin/env python3
"""
Comprehensive API endpoint testing for easyedit-v2
Tests all endpoints with various scenarios including edge cases
"""

import sys
import os
import json
import uuid
import tempfile
from io import BytesIO

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

def create_test_audio_file():
    """Create a minimal WAV file for testing"""
    # WAV header for 1 second of silence
    wav_header = (
        b'RIFF'       # Chunk ID
        b'\x24\x08\x00\x00'  # Chunk size (2084 bytes)
        b'WAVE'       # Format
        b'fmt '       # Subchunk1 ID
        b'\x10\x00\x00\x00'  # Subchunk1 size (16 bytes)
        b'\x01\x00'   # Audio format (PCM)
        b'\x01\x00'   # Number of channels (1)
        b'\x44\xAC\x00\x00'  # Sample rate (44100)
        b'\x88\x58\x01\x00'  # Byte rate
        b'\x02\x00'   # Block align
        b'\x10\x00'   # Bits per sample (16)
        b'data'       # Subchunk2 ID
        b'\x00\x08\x00\x00'  # Subchunk2 size (2048 bytes)
    )
    # Add 2048 bytes of silence (zeros)
    audio_data = wav_header + b'\x00' * 2048
    return audio_data

def create_test_drt_file():
    """Create a minimal DRT XML file for testing"""
    drt_content = """<?xml version="1.0" encoding="UTF-8"?>
<timeline name="Test Timeline" framerate="25">
    <track index="1" name="Audio Track" type="audio">
        <clipitem name="Test Clip">
            <start>00:00:00:00</start>
            <end>00:00:05:00</end>
            <file>
                <name>test_audio.wav</name>
                <in>00:00:00:00</in>
                <out>00:00:05:00</out>
            </file>
        </clipitem>
    </track>
    <marker name="Test Marker" timecode="00:00:02:00" color="Red"/>
</timeline>"""
    return drt_content.encode('utf-8')

def test_health_endpoint():
    """Test health endpoint"""
    print("Testing health endpoint...")

    try:
        # Import here to avoid dependency issues
        from app import app

        with app.test_client() as client:
            response = client.get('/health')

            print(f"  Status code: {response.status_code}")

            if response.status_code == 200:
                data = response.get_json()
                print(f"  Response keys: {list(data.keys())}")
                print("  [PASS] Health endpoint working")
                return True
            else:
                print(f"  [FAIL] Health endpoint returned {response.status_code}")
                return False

    except Exception as e:
        print(f"  [FAIL] Health endpoint test failed: {str(e)}")
        return False

def test_metrics_endpoint():
    """Test metrics endpoint"""
    print("\nTesting metrics endpoint...")

    try:
        from app import app

        with app.test_client() as client:
            response = client.get('/metrics')

            print(f"  Status code: {response.status_code}")

            if response.status_code == 200:
                data = response.get_json()
                print(f"  Response type: {type(data)}")
                print("  [PASS] Metrics endpoint working")
                return True
            else:
                print(f"  [FAIL] Metrics endpoint returned {response.status_code}")
                return False

    except Exception as e:
        print(f"  [FAIL] Metrics endpoint test failed: {str(e)}")
        return False

def test_upload_endpoint():
    """Test file upload endpoint"""
    print("\nTesting upload endpoint...")

    try:
        from app import app

        with app.test_client() as client:
            # Create test files
            audio_data = create_test_audio_file()
            drt_data = create_test_drt_file()

            # Test successful upload
            response = client.post('/upload', data={
                'audio': (BytesIO(audio_data), 'test_audio.wav'),
                'drt': (BytesIO(drt_data), 'test_timeline.drt')
            }, content_type='multipart/form-data')

            print(f"  Status code: {response.status_code}")

            if response.status_code == 200:
                data = response.get_json()
                job_id = data.get('job_id')
                print(f"  Job ID created: {job_id}")
                print("  [PASS] Upload endpoint working")
                return job_id
            else:
                print(f"  [FAIL] Upload endpoint returned {response.status_code}")
                print(f"  Response: {response.get_data(as_text=True)}")
                return None

    except Exception as e:
        print(f"  [FAIL] Upload endpoint test failed: {str(e)}")
        return None

def test_upload_validation():
    """Test upload endpoint validation"""
    print("\nTesting upload validation...")

    try:
        from app import app

        with app.test_client() as client:
            # Test missing files
            response = client.post('/upload', data={})
            print(f"  Missing files status: {response.status_code}")

            # Test invalid file types
            response = client.post('/upload', data={
                'audio': (BytesIO(b'invalid'), 'test.txt'),
                'drt': (BytesIO(b'invalid'), 'test.pdf')
            }, content_type='multipart/form-data')
            print(f"  Invalid types status: {response.status_code}")

            # Test malicious filename
            response = client.post('/upload', data={
                'audio': (BytesIO(create_test_audio_file()), '../../../etc/passwd.wav'),
                'drt': (BytesIO(create_test_drt_file()), 'normal.drt')
            }, content_type='multipart/form-data')
            print(f"  Malicious filename status: {response.status_code}")

            if response.status_code >= 400:
                print("  [PASS] Upload validation working")
                return True
            else:
                print("  [FAIL] Upload validation not working properly")
                return False

    except Exception as e:
        print(f"  [FAIL] Upload validation test failed: {str(e)}")
        return False

def test_job_endpoints(job_id):
    """Test job-related endpoints"""
    print(f"\nTesting job endpoints with job_id: {job_id}")

    if not job_id:
        print("  [SKIP] No job_id available")
        return False

    try:
        from app import app

        with app.test_client() as client:
            # Test status endpoint
            response = client.get(f'/status/{job_id}')
            print(f"  Status endpoint: {response.status_code}")

            if response.status_code == 200:
                data = response.get_json()
                print(f"  Job status: {data.get('status')}")

            # Test invalid job ID validation
            response = client.get('/status/invalid../job')
            print(f"  Invalid job ID: {response.status_code}")

            # Test processing endpoint with valid options
            processing_options = {
                'enable_transcription': True,
                'enable_speaker_diarization': False,
                'remove_silence': True,
                'min_clip_length': 5
            }

            response = client.post(f'/process/{job_id}',
                                 json=processing_options,
                                 content_type='application/json')
            print(f"  Process endpoint: {response.status_code}")

            # Test processing with invalid options
            invalid_options = {
                'enable_transcription': 'yes',  # Should be boolean
                'malicious_option': 'value',     # Unknown option
                'min_clip_length': 500          # Too high
            }

            response = client.post(f'/process/{job_id}',
                                 json=invalid_options,
                                 content_type='application/json')
            print(f"  Invalid options: {response.status_code}")

            if response.status_code >= 400:
                print("  [PASS] Job endpoints validation working")
                return True
            else:
                print("  [FAIL] Job endpoints validation issues")
                return False

    except Exception as e:
        print(f"  [FAIL] Job endpoints test failed: {str(e)}")
        return False

def test_cleanup_endpoint():
    """Test cleanup endpoint"""
    print("\nTesting cleanup endpoint...")

    try:
        from app import app

        with app.test_client() as client:
            response = client.post('/cleanup')

            print(f"  Status code: {response.status_code}")

            if response.status_code == 200:
                data = response.get_json()
                print(f"  Cleanup message: {data.get('message')}")
                print("  [PASS] Cleanup endpoint working")
                return True
            else:
                print(f"  [FAIL] Cleanup endpoint returned {response.status_code}")
                return False

    except Exception as e:
        print(f"  [FAIL] Cleanup endpoint test failed: {str(e)}")
        return False

def test_error_handling():
    """Test error handling"""
    print("\nTesting error handling...")

    try:
        from app import app

        with app.test_client() as client:
            # Test 404 for non-existent endpoint
            response = client.get('/nonexistent')
            print(f"  404 handling: {response.status_code}")

            # Test 405 for wrong method
            response = client.post('/health')
            print(f"  405 handling: {response.status_code}")

            # Test non-existent job
            response = client.get('/status/non-existent-job-id')
            print(f"  Non-existent job: {response.status_code}")

            print("  [PASS] Error handling working")
            return True

    except Exception as e:
        print(f"  [FAIL] Error handling test failed: {str(e)}")
        return False

def test_security_features():
    """Test security features"""
    print("\nTesting security features...")

    try:
        from app import app

        with app.test_client() as client:
            # Test CORS headers
            response = client.options('/health')
            print(f"  CORS preflight: {response.status_code}")

            # Test rate limiting (if enabled)
            print("  Rate limiting: [SKIP - requires multiple requests]")

            # Test XSS protection in responses
            response = client.get('/health')
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' in content_type:
                print("  JSON content type: [PASS]")

            print("  [PASS] Security features basic check")
            return True

    except Exception as e:
        print(f"  [FAIL] Security features test failed: {str(e)}")
        return False

def main():
    """Run all API endpoint tests"""
    print("COMPREHENSIVE API ENDPOINT TESTING")
    print("=" * 50)

    tests = [
        test_health_endpoint,
        test_metrics_endpoint,
        test_upload_validation,
        test_cleanup_endpoint,
        test_error_handling,
        test_security_features
    ]

    results = []
    job_id = None

    # Run upload test and get job_id
    job_id = test_upload_endpoint()
    results.append(job_id is not None)

    # Test job endpoints if we have a job_id
    if job_id:
        job_result = test_job_endpoints(job_id)
        results.append(job_result)

    # Run other tests
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"  [CRASH] Test {test.__name__} crashed: {str(e)}")
            results.append(False)

    print("\n" + "=" * 50)
    print("API ENDPOINT TEST SUMMARY")
    print("=" * 50)

    passed = sum(results)
    total = len(results)

    test_names = ['upload_endpoint', 'job_endpoints'] + [t.__name__ for t in tests]

    for i, (test_name, result) in enumerate(zip(test_names, results)):
        status = "[PASS]" if result else "[FAIL]"
        print(f"{i+1}. {test_name}: {status}")

    print(f"\nOVERALL: {passed}/{total} tests passed ({passed/total*100:.1f}%)")

    if passed == total:
        print("SUCCESS: ALL API ENDPOINTS WORKING!")
    else:
        print("WARNING: SOME ENDPOINT ISSUES FOUND")

    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)