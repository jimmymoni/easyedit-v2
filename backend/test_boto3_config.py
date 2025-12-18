"""
Test boto3 S3 client configuration to debug presigned URL issues
"""
import boto3
from botocore.client import Config
import os
from dotenv import load_dotenv

load_dotenv()

print("\n" + "=" * 60)
print("Boto3 S3 Client Configuration Test")
print("=" * 60)

# Test different S3 client configurations
configs_to_test = [
    ("Default config", {}),
    ("With signature_version='s3v4'", {'config': Config(signature_version='s3v4')}),
    ("With endpoint_url specified", {'endpoint_url': f"https://s3.{os.getenv('AWS_REGION')}.amazonaws.com"}),
    ("With use_dualstack_endpoint=False", {'config': Config(s3={'use_dualstack_endpoint': False})}),
]

bucket = os.getenv('S3_VIDEO_BUCKET')
region = os.getenv('AWS_REGION')

for name, kwargs in configs_to_test:
    print(f"\n[{name}]")

    try:
        # Create S3 client with specific config
        s3 = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=region,
            **kwargs
        )

        # Generate presigned URL
        url = s3.generate_presigned_url(
            'put_object',
            Params={'Bucket': bucket, 'Key': 'test-config/test.txt'},
            ExpiresIn=60
        )

        print(f"  URL format: {url[:100]}...")
        print(f"  Endpoint in URL: {url.split('?')[0].split('/')[2]}")

    except Exception as e:
        print(f"  [FAIL] {e}")

print("\n" + "=" * 60)
