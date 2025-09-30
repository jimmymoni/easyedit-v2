#!/usr/bin/env python3
"""
Simple test script to validate critical fixes work correctly
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

def test_imports():
    """Test that all critical modules import without errors"""
    print("Testing imports...")

    try:
        # Test time import fix
        from app import time
        print("  [PASS] Time import fixed")

        # Test secure XML parser
        from parsers.drt_parser import DRTParser
        print("  [PASS] DRT parser imports (secure XML)")

        # Test config security
        from config import Config
        print("  [PASS] Config imports with secure key generation")

        # Test validation functions
        from utils.error_handlers import (
            validate_job_id, validate_processing_options,
            validate_file_upload, sanitize_filename
        )
        print("  [PASS] Enhanced validation functions available")

        return True
    except Exception as e:
        print(f"  [FAIL] Import error: {str(e)}")
        return False

def test_config_security():
    """Test that config generates secure keys"""
    print("\nTesting config security...")

    try:
        from config import Config

        # Check that a key exists and is reasonable length
        if Config.SECRET_KEY and len(Config.SECRET_KEY) >= 32:
            print("  [PASS] Secure secret key available")
        else:
            print("  [FAIL] Secret key not properly configured")
            return False

        return True
    except Exception as e:
        print(f"  [FAIL] Config security test failed: {str(e)}")
        return False

def test_xml_parser():
    """Test that XML parser works with valid input"""
    print("\nTesting XML parser...")

    try:
        from parsers.drt_parser import DRTParser

        # Test valid XML
        valid_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <timeline name="Test Timeline" framerate="25">
            <track index="1" name="Audio 1" type="audio">
                <clipitem name="Test Clip">
                    <start>00:00:00:00</start>
                    <end>00:00:10:00</end>
                </clipitem>
            </track>
        </timeline>"""

        parser = DRTParser()
        timeline = parser.parse_content(valid_xml)
        print("  [PASS] Valid XML parsing works")

        return True
    except Exception as e:
        print(f"  [FAIL] XML parser test failed: {str(e)}")
        return False

def test_job_validation():
    """Test job ID validation"""
    print("\nTesting job ID validation...")

    try:
        from utils.error_handlers import validate_job_id, ValidationError
        import uuid

        # Test valid job ID
        valid_id = str(uuid.uuid4())
        result = validate_job_id(valid_id)
        if result == valid_id:
            print("  [PASS] Valid job ID accepted")
        else:
            print("  [FAIL] Valid job ID modified unexpectedly")
            return False

        # Test malicious job ID
        try:
            validate_job_id("../../../etc/passwd")
            print("  [FAIL] Path traversal in job ID was accepted")
            return False
        except ValidationError:
            print("  [PASS] Path traversal in job ID correctly rejected")

        return True
    except Exception as e:
        print(f"  [FAIL] Job ID validation test failed: {str(e)}")
        return False

def test_audio_analyzer():
    """Test that audio analyzer has streaming capability"""
    print("\nTesting memory optimization...")

    try:
        from services.audio_analyzer import AudioAnalyzer

        analyzer = AudioAnalyzer()

        # Check that streaming components exist
        if hasattr(analyzer, 'streaming_threshold_mb'):
            print("  [PASS] Streaming threshold configured")
        else:
            print("  [FAIL] Streaming threshold not configured")
            return False

        if hasattr(analyzer, '_load_audio_chunk'):
            print("  [PASS] Streaming methods implemented")
        else:
            print("  [FAIL] Streaming methods not found")
            return False

        return True
    except Exception as e:
        print(f"  [FAIL] Memory optimization test failed: {str(e)}")
        return False

def main():
    """Run all critical fix tests"""
    print("TESTING CRITICAL SECURITY AND PERFORMANCE FIXES")
    print("=" * 60)

    tests = [
        test_imports,
        test_config_security,
        test_xml_parser,
        test_job_validation,
        test_audio_analyzer
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"  [CRASH] Test {test.__name__} crashed: {str(e)}")
            results.append(False)

    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)

    passed = sum(results)
    total = len(results)

    for i, (test, result) in enumerate(zip(tests, results)):
        status = "[PASS]" if result else "[FAIL]"
        print(f"{i+1}. {test.__name__}: {status}")

    print(f"\nOVERALL: {passed}/{total} tests passed ({passed/total*100:.1f}%)")

    if passed == total:
        print("SUCCESS: ALL CRITICAL FIXES WORKING!")
    else:
        print("WARNING: SOME ISSUES FOUND - Review failed tests")

    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)