"""
Simplest possible presigned URL test
"""
import boto3
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Create S3 client with explicit regional endpoint
region = os.getenv('AWS_REGION')
s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=region,
    endpoint_url=f'https://s3.{region}.amazonaws.com'
)

bucket = os.getenv('S3_VIDEO_BUCKET')
test_key = 'test-simple/test.txt'

print("\n=== Simple Presigned URL Test ===\n")

# Generate presigned URL (most basic)
url = s3.generate_presigned_url(
    'put_object',
    Params={'Bucket': bucket, 'Key': test_key},
    ExpiresIn=300
)

print(f"URL: {url[:80]}...")

# Upload (most basic)
response = requests.put(url, data=b'test')

print(f"Status: {response.status_code}")

if response.status_code == 200:
    print("[OK] Upload worked!")
    # Cleanup
    s3.delete_object(Bucket=bucket, Key=test_key)
else:
    print(f"[FAIL] {response.text[:200]}")
