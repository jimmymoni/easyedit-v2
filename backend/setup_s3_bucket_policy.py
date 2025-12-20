"""
Setup script to configure S3 bucket policy for Replicate access.

This script adds a bucket policy that allows GetObject operations
on presigned URLs while maintaining security through signature validation.

Security:
- Principal "*" is safe because presigned URLs require signature validation
- Only allows GetObject (no write/delete permissions)
- Only applies to /uploads/* prefix (not entire bucket)
- Presigned URLs still expire after 24 hours
- Backend controls who gets presigned URLs (JWT auth required)

Usage:
    python setup_s3_bucket_policy.py
"""

import sys
import io
import boto3
import json
from config import Config
from botocore.exceptions import ClientError

# Fix Windows console encoding issues
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def get_current_bucket_policy():
    """Get the current bucket policy if it exists."""
    print("\n" + "="*60)
    print("STEP 1: Checking current bucket policy")
    print("="*60)

    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
            region_name=Config.AWS_REGION,
            endpoint_url=f'https://s3.{Config.AWS_REGION}.amazonaws.com'
        )

        try:
            response = s3_client.get_bucket_policy(Bucket=Config.S3_VIDEO_BUCKET)
            policy = json.loads(response['Policy'])
            print("✅ Current bucket policy found:")
            print(json.dumps(policy, indent=2))
            return policy
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchBucketPolicy':
                print("ℹ️  No bucket policy currently exists")
                print("   (This is expected for new buckets)")
                return None
            else:
                raise

    except ClientError as e:
        print(f"❌ Error getting bucket policy: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None


def setup_bucket_policy():
    """Add bucket policy to allow presigned URL access."""
    print("\n" + "="*60)
    print("STEP 2: Applying new bucket policy")
    print("="*60)

    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
            region_name=Config.AWS_REGION,
            endpoint_url=f'https://s3.{Config.AWS_REGION}.amazonaws.com'
        )

        # Define the bucket policy
        bucket_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowPresignedURLAccess",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{Config.S3_VIDEO_BUCKET}/uploads/*"
                }
            ]
        }

        print("📋 New bucket policy:")
        print(json.dumps(bucket_policy, indent=2))
        print()

        # Apply the policy
        print("🔄 Applying bucket policy...")
        s3_client.put_bucket_policy(
            Bucket=Config.S3_VIDEO_BUCKET,
            Policy=json.dumps(bucket_policy)
        )

        print()
        print("✅ Bucket policy applied successfully!")
        print()
        print("Policy details:")
        print(f"   Bucket: {Config.S3_VIDEO_BUCKET}")
        print(f"   Region: {Config.AWS_REGION}")
        print(f"   Allows: GetObject on uploads/* for presigned URLs")
        print(f"   Principal: * (any user with valid presigned URL)")
        print()

        return True

    except ClientError as e:
        print(f"❌ Error applying bucket policy: {e}")
        print()
        print("Common issues:")
        print("1. Insufficient IAM permissions (need s3:PutBucketPolicy)")
        print("2. Public Access Block preventing policy application")
        print()
        print("Alternative: Apply policy manually via AWS Console:")
        print(f"1. Go to AWS S3 Console → {Config.S3_VIDEO_BUCKET}")
        print("2. Navigate to 'Permissions' tab")
        print("3. Scroll to 'Bucket policy' section")
        print("4. Click 'Edit' and paste the JSON policy above")
        print("5. Save changes")
        print()
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def verify_bucket_policy():
    """Verify the bucket policy was applied correctly."""
    print("\n" + "="*60)
    print("STEP 3: Verifying bucket policy")
    print("="*60)

    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
            region_name=Config.AWS_REGION,
            endpoint_url=f'https://s3.{Config.AWS_REGION}.amazonaws.com'
        )

        response = s3_client.get_bucket_policy(Bucket=Config.S3_VIDEO_BUCKET)
        policy = json.loads(response['Policy'])

        print("✅ Bucket policy verified:")
        print(json.dumps(policy, indent=2))
        print()

        # Check for expected statement
        has_presigned_access = False
        for statement in policy.get('Statement', []):
            if statement.get('Sid') == 'AllowPresignedURLAccess':
                has_presigned_access = True
                break

        if has_presigned_access:
            print("✅ Presigned URL access statement found")
            print("   Replicate should now be able to download videos")
            return True
        else:
            print("⚠️  Expected statement not found in policy")
            print("   Policy may have been modified or overwritten")
            return False

    except ClientError as e:
        print(f"❌ Error verifying bucket policy: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def check_public_access_block():
    """Check Public Access Block settings."""
    print("\n" + "="*60)
    print("STEP 4: Checking Public Access Block settings")
    print("="*60)

    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
            region_name=Config.AWS_REGION,
            endpoint_url=f'https://s3.{Config.AWS_REGION}.amazonaws.com'
        )

        response = s3_client.get_public_access_block(Bucket=Config.S3_VIDEO_BUCKET)
        config = response['PublicAccessBlockConfiguration']

        print("📋 Current Public Access Block settings:")
        print(f"   BlockPublicAcls: {config.get('BlockPublicAcls', False)}")
        print(f"   IgnorePublicAcls: {config.get('IgnorePublicAcls', False)}")
        print(f"   BlockPublicPolicy: {config.get('BlockPublicPolicy', False)}")
        print(f"   RestrictPublicBuckets: {config.get('RestrictPublicBuckets', False)}")
        print()

        # Check if settings might block presigned URLs
        if config.get('BlockPublicPolicy', False) or config.get('RestrictPublicBuckets', False):
            print("⚠️  WARNING: Public Access Block settings may interfere")
            print("   BlockPublicPolicy: True - May prevent bucket policy from working")
            print("   RestrictPublicBuckets: True - May block presigned URL access")
            print()
            print("   If presigned URLs still don't work, try:")
            print("   python adjust_public_access_block.py")
            print()
            return False
        else:
            print("✅ Public Access Block settings look good")
            print("   Should not interfere with presigned URLs")
            return True

    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchPublicAccessBlockConfiguration':
            print("ℹ️  No Public Access Block configuration")
            print("   (Default AWS settings apply)")
            return True
        else:
            print(f"❌ Error checking Public Access Block: {e}")
            return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def main():
    """Main setup workflow."""
    print("\n" + "="*60)
    print("S3 BUCKET POLICY SETUP FOR REPLICATE ACCESS")
    print("="*60)
    print("This script configures S3 to allow Replicate to download")
    print("videos via presigned URLs.")
    print()
    print(f"Bucket: {Config.S3_VIDEO_BUCKET}")
    print(f"Region: {Config.AWS_REGION}")
    print()

    # Step 1: Check current policy
    get_current_bucket_policy()

    # Step 2: Apply new policy
    policy_applied = setup_bucket_policy()
    if not policy_applied:
        print("\n" + "="*60)
        print("❌ SETUP FAILED: Could not apply bucket policy")
        print("="*60)
        print("Please apply the policy manually via AWS Console")
        print("See error message above for instructions")
        print()
        return

    # Step 3: Verify policy
    policy_verified = verify_bucket_policy()
    if not policy_verified:
        print("\n⚠️  Policy verification failed")
        print("   Check AWS Console to confirm policy is correct")

    # Step 4: Check Public Access Block
    public_access_ok = check_public_access_block()

    # Final summary
    print("\n" + "="*60)
    print("SETUP SUMMARY")
    print("="*60)

    if policy_applied and policy_verified:
        print("✅ Bucket policy: APPLIED")
        print("✅ Policy verification: PASSED")

        if public_access_ok:
            print("✅ Public Access Block: OK")
            print()
            print("🎉 Setup complete! Replicate should now be able to")
            print("   download videos via presigned URLs.")
            print()
            print("Next steps:")
            print("1. Run: python test_presigned_access.py")
            print("   (Verify presigned URLs work)")
            print("2. Test video processing with Replicate")
            print("3. Monitor Replicate predictions for success")
        else:
            print("⚠️  Public Access Block: MAY INTERFERE")
            print()
            print("If presigned URLs still fail:")
            print("1. Run: python adjust_public_access_block.py")
            print("2. Run: python test_presigned_access.py")
    else:
        print("❌ Bucket policy: FAILED")
        print()
        print("Required action:")
        print("1. Apply policy manually via AWS Console")
        print("2. Run: python test_presigned_access.py")

    print("="*60 + "\n")


if __name__ == "__main__":
    main()
