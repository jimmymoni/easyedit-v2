"""
Test pre-signed URL generation directly
"""
import boto3
import os
import requests
from dotenv import load_dotenv

load_dotenv()

# Create S3 client with credentials from .env and regional endpoint
region = os.getenv('AWS_REGION')
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=region,
    endpoint_url=f'https://s3.{region}.amazonaws.com'
)

bucket = os.getenv('S3_VIDEO_BUCKET')
test_key = f"test-presigned/test-{os.urandom(4).hex()}.txt"

print("\n" + "=" * 60)
print("Pre-signed URL Test")
print("=" * 60)

# Test 1: Direct put_object (should work based on test_aws_credentials.py)
print("\n[1] Testing direct put_object...")
try:
    s3_client.put_object(
        Bucket=bucket,
        Key=test_key,
        Body=b"Test content from direct put"
    )
    print(f"    [OK] Direct put_object works!")
except Exception as e:
    print(f"    [FAIL] Direct put failed: {e}")
    exit(1)

# Test 2: Generate pre-signed URL for PUT
print("\n[2] Generating pre-signed URL for PUT...")
try:
    presigned_url = s3_client.generate_presigned_url(
        'put_object',
        Params={
            'Bucket': bucket,
            'Key': test_key + '-presigned'
            # Don't specify ContentType - let client send what it wants
        },
        ExpiresIn=3600  # 1 hour
    )
    print(f"    [OK] Pre-signed URL generated")
    print(f"    URL: {presigned_url[:80]}...")
except Exception as e:
    print(f"    [FAIL] Failed to generate URL: {e}")
    exit(1)

# Test 3: Upload using pre-signed URL
print("\n[3] Testing upload with pre-signed URL...")
try:
    response = requests.put(
        presigned_url,
        data=b"Test content from pre-signed URL"
        # Don't specify Content-Type header - requests will handle it
    )
    if response.status_code == 200:
        print(f"    [OK] Pre-signed URL upload works!")
        print(f"    ETag: {response.headers.get('ETag')}")
    else:
        print(f"    [FAIL] Upload failed: {response.status_code}")
        print(f"    Response: {response.text[:500]}")
        exit(1)
except Exception as e:
    print(f"    [FAIL] Request failed: {e}")
    exit(1)

# Cleanup
print("\n[4] Cleaning up...")
s3_client.delete_object(Bucket=bucket, Key=test_key)
s3_client.delete_object(Bucket=bucket, Key=test_key + '-presigned')
print("    [OK] Test files deleted")

print("\n" + "=" * 60)
print("[SUCCESS] Pre-signed URLs are working correctly!")
print("=" * 60 + "\n")
