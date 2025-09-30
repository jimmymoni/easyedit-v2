#!/usr/bin/env python3
"""
Test script for authentication and rate limiting functionality
"""

import requests
import json
import time
import os
import sys
from typing import Dict, Any

BASE_URL = "http://localhost:5000"

class AuthTestClient:
    """Test client for authentication endpoints"""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.access_token = None
        self.refresh_token = None

    def test_health(self) -> bool:
        """Test if server is running"""
        try:
            response = self.session.get(f"{self.base_url}/health")
            return response.status_code == 200
        except requests.exceptions.ConnectionError:
            return False

    def get_demo_token(self) -> Dict[str, Any]:
        """Get demo authentication token"""
        response = self.session.get(f"{self.base_url}/auth/demo-token")

        if response.status_code == 200:
            data = response.json()
            self.access_token = data.get('access_token')
            self.refresh_token = data.get('refresh_token')

            # Set authorization header for future requests
            self.session.headers.update({
                'Authorization': f"Bearer {self.access_token}"
            })

            return data
        else:
            raise Exception(f"Failed to get demo token: {response.text}")

    def verify_token(self) -> Dict[str, Any]:
        """Verify current token"""
        response = self.session.get(f"{self.base_url}/auth/verify")

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Token verification failed: {response.text}")

    def refresh_access_token(self) -> Dict[str, Any]:
        """Refresh access token"""
        if not self.refresh_token:
            raise Exception("No refresh token available")

        response = self.session.post(
            f"{self.base_url}/auth/refresh",
            json={'refresh_token': self.refresh_token}
        )

        if response.status_code == 200:
            data = response.json()
            self.access_token = data.get('access_token')
            self.refresh_token = data.get('refresh_token')

            # Update authorization header
            self.session.headers.update({
                'Authorization': f"Bearer {self.access_token}"
            })

            return data
        else:
            raise Exception(f"Token refresh failed: {response.text}")

    def get_rate_limits(self) -> Dict[str, Any]:
        """Get current rate limit status"""
        response = self.session.get(f"{self.base_url}/auth/rate-limits")

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get rate limits: {response.text}")

    def test_protected_endpoint(self, endpoint: str) -> Dict[str, Any]:
        """Test a protected endpoint"""
        response = self.session.get(f"{self.base_url}{endpoint}")

        return {
            'endpoint': endpoint,
            'status_code': response.status_code,
            'response': response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
        }

    def test_rate_limiting(self, endpoint: str = '/auth/demo-token', limit: int = 15) -> Dict[str, Any]:
        """Test rate limiting by making multiple requests"""
        results = []

        print(f"Testing rate limiting on {endpoint} with {limit} requests...")

        for i in range(limit):
            start_time = time.time()
            response = self.session.get(f"{self.base_url}{endpoint}")
            end_time = time.time()

            result = {
                'request_number': i + 1,
                'status_code': response.status_code,
                'response_time': end_time - start_time,
                'headers': {
                    'X-RateLimit-Limit': response.headers.get('X-RateLimit-Limit'),
                    'X-RateLimit-Remaining': response.headers.get('X-RateLimit-Remaining'),
                    'X-RateLimit-Reset': response.headers.get('X-RateLimit-Reset'),
                    'Retry-After': response.headers.get('Retry-After')
                }
            }

            if response.status_code == 429:
                result['rate_limited'] = True
                print(f"Rate limited on request {i + 1}")
                break
            else:
                result['rate_limited'] = False

            results.append(result)
            time.sleep(0.1)  # Small delay between requests

        return results

def run_authentication_tests():
    """Run comprehensive authentication tests"""
    print("Starting Authentication and Rate Limiting Tests")
    print("=" * 50)

    client = AuthTestClient()

    # Test 1: Check if server is running
    print("1. Testing server health...")
    if not client.test_health():
        print("[FAIL] Server is not running or not responding")
        print("Please start the server with: python app.py")
        return False
    print("[PASS] Server is running")

    # Test 2: Get demo token
    print("\n2. Testing demo token generation...")
    try:
        token_data = client.get_demo_token()
        print("[PASS] Demo token generated successfully")
        print(f"   Access token: {token_data['access_token'][:50]}...")
        print(f"   Expires in: {token_data['expires_in']} seconds")
        print(f"   Token type: {token_data['token_type']}")
    except Exception as e:
        print(f"[FAIL] Demo token generation failed: {str(e)}")
        return False

    # Test 3: Verify token
    print("\n3. Testing token verification...")
    try:
        verify_data = client.verify_token()
        print("[PASS] Token verification successful")
        print(f"   User ID: {verify_data['user']['user_id']}")
        print(f"   Email: {verify_data['user']['email']}")
        print(f"   Role: {verify_data['user']['role']}")
        print(f"   Has API Key: {verify_data['user']['has_api_key']}")
    except Exception as e:
        print(f"[FAIL] Token verification failed: {str(e)}")
        return False

    # Test 4: Get rate limits
    print("\n4. Testing rate limit status...")
    try:
        rate_limits = client.get_rate_limits()
        print("[PASS] Rate limit status retrieved")
        print(f"   Client tier: {rate_limits['tier']}")
        print(f"   General limit: {rate_limits['limits']['general']}")
        print(f"   Upload limit: {rate_limits['limits']['upload']}")
        print(f"   Processing limit: {rate_limits['limits']['processing']}")
    except Exception as e:
        print(f"[FAIL] Rate limit status failed: {str(e)}")
        return False

    # Test 5: Test protected endpoints without auth
    print("\n5. Testing protected endpoints without authentication...")
    no_auth_client = AuthTestClient()

    protected_endpoints = ['/protected/test', '/protected/upload']

    for endpoint in protected_endpoints:
        result = no_auth_client.test_protected_endpoint(endpoint)
        if result['status_code'] == 401:
            print(f"[PASS] {endpoint} properly protected (401 Unauthorized)")
        else:
            print(f"[FAIL] {endpoint} not properly protected (got {result['status_code']})")

    # Test 6: Test rate limiting
    print("\n6. Testing rate limiting...")
    try:
        rate_test_results = client.test_rate_limiting('/auth/demo-token', 15)

        rate_limited = any(r['rate_limited'] for r in rate_test_results)
        if rate_limited:
            print("[PASS] Rate limiting is working")
            successful_requests = len([r for r in rate_test_results if not r['rate_limited']])
            print(f"   Successful requests before rate limit: {successful_requests}")
        else:
            print("[WARN] Rate limiting not triggered (may need more requests)")
    except Exception as e:
        print(f"[FAIL] Rate limiting test failed: {str(e)}")

    # Test 7: Test token refresh
    print("\n7. Testing token refresh...")
    try:
        refresh_data = client.refresh_access_token()
        print("[PASS] Token refresh successful")
        print(f"   New access token: {refresh_data['access_token'][:50]}...")
    except Exception as e:
        print(f"[FAIL] Token refresh failed: {str(e)}")

    print("\n" + "=" * 50)
    print("Authentication and Rate Limiting Tests Complete")
    return True

if __name__ == "__main__":
    success = run_authentication_tests()
    sys.exit(0 if success else 1)