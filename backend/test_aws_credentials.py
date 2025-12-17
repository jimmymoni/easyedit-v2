"""
Quick test to verify AWS credentials and S3 bucket
"""
import boto3
from botocore.exceptions import ClientError
import os
from dotenv import load_dotenv

# Load .env
load_dotenv()

print("\n" + "=" * 60)
print("AWS Credentials Test")
print("=" * 60)

# Get credentials from .env
access_key = os.getenv('AWS_ACCESS_KEY_ID')
secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
region = os.getenv('AWS_REGION')
bucket_name = os.getenv('S3_VIDEO_BUCKET')

print(f"\n[1] Reading .env file...")
print(f"    AWS_ACCESS_KEY_ID: {access_key[:10]}... (first 10 chars)")
print(f"    AWS_SECRET_ACCESS_KEY: {secret_key[:10]}... (first 10 chars)")
print(f"    AWS_REGION: {region}")
print(f"    S3_VIDEO_BUCKET: {bucket_name}")

# Test 1: Can we create S3 client?
print(f"\n[2] Creating S3 client...")
try:
    s3_client = boto3.client(
        's3',
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region
    )
    print(f"    [OK] S3 client created")
except Exception as e:
    print(f"    [FAIL] Could not create S3 client: {e}")
    exit(1)

# Test 2: Can we authenticate with AWS?
print(f"\n[3] Testing AWS credentials...")
try:
    # Try to list buckets (this will fail if credentials are wrong)
    response = s3_client.list_buckets()
    print(f"    [OK] Credentials are VALID!")
    print(f"    Found {len(response['Buckets'])} buckets in your AWS account:")
    for bucket in response['Buckets']:
        print(f"      - {bucket['Name']}")
except ClientError as e:
    error_code = e.response['Error']['Code']
    print(f"    [FAIL] AWS rejected credentials: {error_code}")
    print(f"    Error: {e.response['Error']['Message']}")
    print(f"\n    This means:")
    if error_code == 'InvalidAccessKeyId':
        print(f"      - Your AWS_ACCESS_KEY_ID is wrong/doesn't exist")
        print(f"      - Go to AWS Console -> IAM -> Users -> Security credentials")
        print(f"      - Create NEW access key and update .env")
    elif error_code == 'SignatureDoesNotMatch':
        print(f"      - Your AWS_SECRET_ACCESS_KEY is wrong")
        print(f"      - Create NEW access key in AWS Console")
    exit(1)

# Test 3: Does the bucket exist?
print(f"\n[4] Checking if bucket '{bucket_name}' exists...")
try:
    s3_client.head_bucket(Bucket=bucket_name)
    print(f"    [OK] Bucket EXISTS and you have access!")
except ClientError as e:
    error_code = e.response['Error']['Code']
    if error_code == '404':
        print(f"    [FAIL] Bucket does NOT exist")
        print(f"    Create it: AWS Console -> S3 -> Create bucket")
        print(f"      Name: {bucket_name}")
        print(f"      Region: {region}")
    elif error_code == '403':
        print(f"    [FAIL] Bucket exists but you don't have permission")
        print(f"    Fix: Add S3 permissions to your IAM user")
    else:
        print(f"    [FAIL] Error: {e.response['Error']['Message']}")
    exit(1)

# Test 4: Can we write to the bucket?
print(f"\n[5] Testing write permission...")
try:
    test_key = "test-upload/test.txt"
    s3_client.put_object(
        Bucket=bucket_name,
        Key=test_key,
        Body=b"Test upload from easyedit-v2"
    )
    print(f"    [OK] Write permission works!")

    # Clean up
    s3_client.delete_object(Bucket=bucket_name, Key=test_key)
    print(f"    [OK] Cleaned up test file")
except ClientError as e:
    print(f"    [FAIL] Cannot write to bucket: {e.response['Error']['Message']}")
    print(f"    Fix: Check IAM permissions (need s3:PutObject)")
    exit(1)

print("\n" + "=" * 60)
print("[SUCCESS] ALL TESTS PASSED!")
print("Your AWS setup is correct and ready to use!")
print("=" * 60 + "\n")
