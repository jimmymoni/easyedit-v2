"""
Check bucket policy for restrictions
"""
import boto3
import json
import os
from dotenv import load_dotenv
from botocore.exceptions import ClientError

load_dotenv()

s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION')
)

bucket = os.getenv('S3_VIDEO_BUCKET')

print("\n" + "=" * 60)
print(f"Bucket Policy Check for: {bucket}")
print("=" * 60)

# Get bucket policy
print("\n[1] Checking bucket policy...")
try:
    policy_response = s3.get_bucket_policy(Bucket=bucket)
    policy = json.loads(policy_response['Policy'])
    print("    Bucket policy exists:")
    print(json.dumps(policy, indent=2))
except ClientError as e:
    if e.response['Error']['Code'] == 'NoSuchBucketPolicy':
        print("    [OK] No bucket policy (this is good for pre-signed URLs)")
    else:
        print(f"    [FAIL] Cannot read policy: {e.response['Error']['Code']}")

# Check bucket ACL
print("\n[2] Checking bucket ACL...")
try:
    acl = s3.get_bucket_acl(Bucket=bucket)
    print(f"    Owner: {acl['Owner']['DisplayName']}")
    print(f"    Grants: {len(acl['Grants'])}")
    for grant in acl['Grants']:
        grantee = grant['Grantee']
        perm = grant['Permission']
        if grantee['Type'] == 'CanonicalUser':
            print(f"      - {grantee.get('DisplayName', 'Unknown')}: {perm}")
        else:
            print(f"      - {grantee['Type']}: {perm}")
except Exception as e:
    print(f"    [FAIL] Cannot read ACL: {e}")

# Check bucket encryption
print("\n[3] Checking bucket encryption...")
try:
    encryption = s3.get_bucket_encryption(Bucket=bucket)
    print(f"    Encryption: {encryption['ServerSideEncryptionConfiguration']['Rules'][0]['ApplyServerSideEncryptionByDefault']['SSEAlgorithm']}")
except ClientError as e:
    if e.response['Error']['Code'] == 'ServerSideEncryptionConfigurationNotFoundError':
        print("    [OK] No encryption configured")
    else:
        print(f"    Error: {e.response['Error']['Code']}")

# Check public access block
print("\n[4] Checking public access block...")
try:
    public_block = s3.get_public_access_block(Bucket=bucket)
    config = public_block['PublicAccessBlockConfiguration']
    print(f"    BlockPublicAcls: {config['BlockPublicAcls']}")
    print(f"    BlockPublicPolicy: {config['BlockPublicPolicy']}")
    print(f"    IgnorePublicAcls: {config['IgnorePublicAcls']}")
    print(f"    RestrictPublicBuckets: {config['RestrictPublicBuckets']}")
except ClientError as e:
    if e.response['Error']['Code'] == 'NoSuchPublicAccessBlockConfiguration':
        print("    [OK] No public access block")
    else:
        print(f"    Error: {e.response['Error']['Code']}")

print("\n" + "=" * 60)
