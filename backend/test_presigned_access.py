"""
Test script to diagnose S3 presigned URL access issues.

This script:
1. Lists existing videos in S3 bucket
2. Generates presigned URL for a test video
3. Attempts to download via HTTP GET
4. Reports success/failure and HTTP status codes

Usage:
    python test_presigned_access.py
"""

import sys
import io
import boto3
import requests
from config import Config
from botocore.exceptions import ClientError

# Fix Windows console encoding issues
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def list_s3_videos():
    """List all videos in the S3 uploads folder."""
    print("\n" + "="*60)
    print("STEP 1: Listing videos in S3 bucket")
    print("="*60)

    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
            region_name=Config.AWS_REGION,
            endpoint_url=f'https://s3.{Config.AWS_REGION}.amazonaws.com'
        )

        response = s3_client.list_objects_v2(
            Bucket=Config.S3_VIDEO_BUCKET,
            Prefix='uploads/',
            MaxKeys=10
        )

        if 'Contents' not in response:
            print("❌ No videos found in S3 bucket")
            print(f"   Bucket: {Config.S3_VIDEO_BUCKET}")
            print(f"   Prefix: uploads/")
            return None

        videos = []
        print(f"✅ Found {len(response['Contents'])} objects:\n")

        for i, obj in enumerate(response['Contents'], 1):
            key = obj['Key']
            size_mb = obj['Size'] / (1024 * 1024)

            # Only list actual video files (not directories)
            if size_mb > 0:
                videos.append({
                    'key': key,
                    'size_mb': size_mb,
                    'last_modified': obj['LastModified']
                })
                print(f"   {i}. {key}")
                print(f"      Size: {size_mb:.2f} MB")
                print(f"      Modified: {obj['LastModified']}")
                print()

        return videos

    except ClientError as e:
        print(f"❌ Error listing S3 objects: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None


def generate_presigned_url(s3_key):
    """Generate presigned URL for the given S3 key."""
    print("\n" + "="*60)
    print("STEP 2: Generating presigned URL")
    print("="*60)

    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
            region_name=Config.AWS_REGION,
            endpoint_url=f'https://s3.{Config.AWS_REGION}.amazonaws.com'
        )

        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': Config.S3_VIDEO_BUCKET,
                'Key': s3_key
            },
            ExpiresIn=86400  # 24 hours
        )

        print(f"✅ Presigned URL generated:")
        print(f"   S3 Key: {s3_key}")
        print(f"   Expiration: 24 hours")
        print(f"   URL: {presigned_url[:100]}...")
        print()

        return presigned_url

    except ClientError as e:
        print(f"❌ Error generating presigned URL: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None


def test_presigned_url_access(presigned_url):
    """Test if the presigned URL is accessible via HTTP GET."""
    print("\n" + "="*60)
    print("STEP 3: Testing presigned URL access")
    print("="*60)

    try:
        print("🔄 Making HTTP GET request to presigned URL...")
        print("   (downloading first 1MB to test access)")
        print()

        # Download only first 1MB to test access (don't download entire file)
        headers = {'Range': 'bytes=0-1048575'}  # First 1MB
        response = requests.get(presigned_url, headers=headers, timeout=30)

        print(f"📊 HTTP Response:")
        print(f"   Status Code: {response.status_code}")
        print(f"   Status Text: {response.reason}")
        print(f"   Content Length: {len(response.content)} bytes")
        print()

        if response.status_code == 200 or response.status_code == 206:
            print("✅ SUCCESS: Presigned URL is accessible!")
            print("   Replicate should be able to download from S3")
            print("   Status: 200 OK or 206 Partial Content")
            return True
        elif response.status_code == 403:
            print("❌ FAILURE: Access Forbidden (403)")
            print("   This is the problem blocking Replicate!")
            print()
            print("   Possible causes:")
            print("   1. S3 Public Access Block is blocking presigned URLs")
            print("   2. Bucket policy is restricting access")
            print("   3. IAM permissions issue")
            print()
            print("   Recommended fix:")
            print("   Run: python setup_s3_bucket_policy.py")
            return False
        else:
            print(f"⚠️ Unexpected status code: {response.status_code}")
            print(f"   Response: {response.text[:500]}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ HTTP request failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def main():
    """Main test workflow."""
    print("\n" + "="*60)
    print("S3 PRESIGNED URL ACCESS DIAGNOSTIC TEST")
    print("="*60)
    print("This script tests if presigned URLs can be accessed")
    print("by external services like Replicate.")
    print()

    # Step 1: List videos in S3
    videos = list_s3_videos()
    if not videos:
        print("\n" + "="*60)
        print("❌ TEST ABORTED: No videos found in S3")
        print("="*60)
        print("\nPlease upload a video first:")
        print("1. Run backend: python app.py")
        print("2. Run frontend: cd ../frontend && npm run dev")
        print("3. Upload a test video via UI")
        print()
        return

    # Use the first video for testing
    test_video = videos[0]
    s3_key = test_video['key']

    # Step 2: Generate presigned URL
    presigned_url = generate_presigned_url(s3_key)
    if not presigned_url:
        print("\n" + "="*60)
        print("❌ TEST ABORTED: Could not generate presigned URL")
        print("="*60)
        return

    # Step 3: Test presigned URL access
    success = test_presigned_url_access(presigned_url)

    # Final summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    if success:
        print("✅ Presigned URL access: WORKING")
        print("✅ S3 configuration: OK")
        print("✅ Replicate should be able to download videos")
        print()
        print("Next steps:")
        print("1. Test video processing with Replicate")
        print("2. Monitor Replicate predictions for success")
    else:
        print("❌ Presigned URL access: BLOCKED")
        print("❌ S3 configuration: NEEDS FIX")
        print("❌ Replicate cannot download videos")
        print()
        print("Required action:")
        print("1. Run: python setup_s3_bucket_policy.py")
        print("   (This will add bucket policy to allow GetObject)")
        print()
        print("Alternative (if above fails):")
        print("2. Run: python adjust_public_access_block.py")
        print("   (This will adjust Public Access Block settings)")

    print("="*60 + "\n")


if __name__ == "__main__":
    main()
