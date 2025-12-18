"""
Test multipart upload pre-signed URLs specifically
"""
import boto3
import os
import requests
from dotenv import load_dotenv

load_dotenv()

region = os.getenv('AWS_REGION')
s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=region,
    endpoint_url=f'https://s3.{region}.amazonaws.com'
)

bucket = os.getenv('S3_VIDEO_BUCKET')
test_key = f"test-multipart/test-{os.urandom(4).hex()}.txt"

print("\n" + "=" * 60)
print("Multipart Upload Pre-signed URL Test")
print("=" * 60)

# Step 1: Create multipart upload
print("\n[1] Creating multipart upload...")
try:
    mp_response = s3.create_multipart_upload(
        Bucket=bucket,
        Key=test_key
    )
    upload_id = mp_response['UploadId']
    print(f"    [OK] Multipart upload created: {upload_id[:20]}...")
except Exception as e:
    print(f"    [FAIL] Cannot create multipart upload: {e}")
    exit(1)

# Step 2: Generate pre-signed URL for upload_part
print("\n[2] Generating pre-signed URL for upload_part...")
try:
    presigned_url = s3.generate_presigned_url(
        'upload_part',
        Params={
            'Bucket': bucket,
            'Key': test_key,
            'UploadId': upload_id,
            'PartNumber': 1
        },
        ExpiresIn=3600
    )
    print(f"    [OK] Pre-signed URL generated")
    print(f"    URL (first 100 chars): {presigned_url[:100]}...")
except Exception as e:
    print(f"    [FAIL] Cannot generate presigned URL: {e}")
    # Cleanup
    s3.abort_multipart_upload(Bucket=bucket, Key=test_key, UploadId=upload_id)
    exit(1)

# Step 3: Upload data using pre-signed URL
print("\n[3] Uploading part using pre-signed URL...")
test_data = b"Test multipart upload data"
try:
    response = requests.put(
        presigned_url,
        data=test_data
    )
    print(f"    Status code: {response.status_code}")

    if response.status_code == 200:
        etag = response.headers.get('ETag', '').strip('"')
        print(f"    [SUCCESS] Upload worked! ETag: {etag}")

        # Complete the multipart upload
        print("\n[4] Completing multipart upload...")
        s3.complete_multipart_upload(
            Bucket=bucket,
            Key=test_key,
            UploadId=upload_id,
            MultipartUpload={
                'Parts': [{'PartNumber': 1, 'ETag': etag}]
            }
        )
        print(f"    [OK] Multipart upload completed")

        # Cleanup
        s3.delete_object(Bucket=bucket, Key=test_key)
        print(f"    [OK] Test file deleted")

    else:
        print(f"    [FAIL] Upload failed: {response.status_code}")
        print(f"    Error: {response.text[:500]}")
        # Cleanup
        s3.abort_multipart_upload(Bucket=bucket, Key=test_key, UploadId=upload_id)

except Exception as e:
    print(f"    [FAIL] Request failed: {e}")
    # Cleanup
    s3.abort_multipart_upload(Bucket=bucket, Key=test_key, UploadId=upload_id)
    exit(1)

print("\n" + "=" * 60)
print("[SUCCESS] Multipart upload pre-signed URLs work!")
print("=" * 60 + "\n")
