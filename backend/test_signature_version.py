"""
Test S3 client with explicit signature version
"""
import boto3
from botocore.client import Config
import os
import requests
from dotenv import load_dotenv

load_dotenv()

bucket = os.getenv('S3_VIDEO_BUCKET')
region = os.getenv('AWS_REGION')

print("\n" + "=" * 60)
print("Signature Version Test")
print("=" * 60)

# Test 1: Default S3 client (what we're currently using)
print("\n[1] Testing default S3 client...")
s3_default = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=region
)

test_key = f"test-sig/default-{os.urandom(4).hex()}.txt"
try:
    url = s3_default.generate_presigned_url(
        'put_object',
        Params={'Bucket': bucket, 'Key': test_key},
        ExpiresIn=3600
    )
    response = requests.put(url, data=b"Test default")
    print(f"    Default client: {response.status_code}")
except Exception as e:
    print(f"    Default client failed: {str(e)[:100]}")

# Test 2: S3 client with explicit signature_version='s3v4'
print("\n[2] Testing S3 client with explicit signature_version='s3v4'...")
s3_v4 = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=region,
    config=Config(signature_version='s3v4')
)

test_key_v4 = f"test-sig/v4-{os.urandom(4).hex()}.txt"
try:
    url_v4 = s3_v4.generate_presigned_url(
        'put_object',
        Params={'Bucket': bucket, 'Key': test_key_v4},
        ExpiresIn=3600
    )
    response_v4 = requests.put(url_v4, data=b"Test s3v4")
    print(f"    S3v4 client: {response_v4.status_code}")
    if response_v4.status_code == 200:
        print("    [SUCCESS] Signature version s3v4 works!")
except Exception as e:
    print(f"    S3v4 client failed: {str(e)[:100]}")

# Test 3: Check what signature version boto3 is using by default
print("\n[3] Checking boto3 configuration...")
print(f"    Region: {region}")
print(f"    Bucket: {bucket}")

print("\n" + "=" * 60)
