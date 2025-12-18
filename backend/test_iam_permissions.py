"""
Test IAM permissions and key status
"""
import boto3
import os
from dotenv import load_dotenv
from botocore.exceptions import ClientError

load_dotenv()

print("\n" + "=" * 60)
print("IAM Permissions Check")
print("=" * 60)

# Create IAM client to check the user's permissions
iam = boto3.client(
    'iam',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION')
)

s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION')
)

# Test 1: Get current user
print("\n[1] Getting current IAM user...")
try:
    user = iam.get_user()
    print(f"    User: {user['User']['UserName']}")
    print(f"    ARN: {user['User']['Arn']}")
    print(f"    Created: {user['User']['CreateDate']}")
except Exception as e:
    print(f"    [FAIL] Cannot get user info: {e}")

# Test 2: List access keys for current user
print("\n[2] Checking access keys...")
try:
    keys = iam.list_access_keys()
    for key in keys['AccessKeyMetadata']:
        current = "(THIS KEY)" if key['AccessKeyId'] == os.getenv('AWS_ACCESS_KEY_ID') else ""
        print(f"    Key: {key['AccessKeyId']} - Status: {key['Status']} {current}")
        if key['AccessKeyId'] == os.getenv('AWS_ACCESS_KEY_ID'):
            if key['Status'] != 'Active':
                print(f"    [ERROR] This key is INACTIVE! Activate it in AWS Console")
except Exception as e:
    print(f"    [FAIL] Cannot list keys: {e}")

# Test 3: Test bucket-level permissions
bucket = os.getenv('S3_VIDEO_BUCKET')
print(f"\n[3] Testing S3 permissions on bucket '{bucket}'...")

# Test PutObject
try:
    s3.put_object(Bucket=bucket, Key='test-perms/test.txt', Body=b'test')
    print(f"    [OK] PutObject: ALLOWED")
    s3.delete_object(Bucket=bucket, Key='test-perms/test.txt')
except ClientError as e:
    print(f"    [FAIL] PutObject: DENIED - {e.response['Error']['Code']}")

# Test GetObject
try:
    # Create a test object first
    s3.put_object(Bucket=bucket, Key='test-perms/get-test.txt', Body=b'test')
    s3.get_object(Bucket=bucket, Key='test-perms/get-test.txt')
    print(f"    [OK] GetObject: ALLOWED")
    s3.delete_object(Bucket=bucket, Key='test-perms/get-test.txt')
except ClientError as e:
    print(f"    [FAIL] GetObject: DENIED - {e.response['Error']['Code']}")

# Test ListBucket
try:
    s3.list_objects_v2(Bucket=bucket, MaxKeys=1)
    print(f"    [OK] ListBucket: ALLOWED")
except ClientError as e:
    print(f"    [FAIL] ListBucket: DENIED - {e.response['Error']['Code']}")

print("\n" + "=" * 60)
print("If all permissions are ALLOWED but pre-signed URLs fail,")
print("check if there's a bucket policy blocking pre-signed URLs")
print("=" * 60 + "\n")
