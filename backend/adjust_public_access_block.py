"""
Fallback script to adjust S3 Public Access Block settings.

This script modifies the Public Access Block configuration to allow
presigned URLs to work. Use this if the bucket policy approach fails.

Changes:
- BlockPublicPolicy: False (allow bucket policies to work)
- RestrictPublicBuckets: False (allow presigned URL access)
- Keep BlockPublicAcls: True (still block public ACLs for security)
- Keep IgnorePublicAcls: True (still ignore public ACLs for security)

Security:
- Presigned URLs still require signature validation
- Backend controls who gets presigned URLs (JWT auth required)
- URLs expire after 24 hours
- Less granular than bucket policy, but still secure

Usage:
    python adjust_public_access_block.py
"""

import sys
import io
import boto3
from config import Config
from botocore.exceptions import ClientError

# Fix Windows console encoding issues
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def get_current_public_access_block():
    """Get current Public Access Block configuration."""
    print("\n" + "="*60)
    print("STEP 1: Checking current Public Access Block settings")
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
            response = s3_client.get_public_access_block(Bucket=Config.S3_VIDEO_BUCKET)
            config = response['PublicAccessBlockConfiguration']

            print("✅ Current Public Access Block configuration:")
            print(f"   BlockPublicAcls: {config.get('BlockPublicAcls', False)}")
            print(f"   IgnorePublicAcls: {config.get('IgnorePublicAcls', False)}")
            print(f"   BlockPublicPolicy: {config.get('BlockPublicPolicy', False)}")
            print(f"   RestrictPublicBuckets: {config.get('RestrictPublicBuckets', False)}")
            print()

            return config

        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchPublicAccessBlockConfiguration':
                print("ℹ️  No Public Access Block configuration exists")
                print("   (Using AWS default settings)")
                return None
            else:
                raise

    except ClientError as e:
        print(f"❌ Error getting Public Access Block: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None


def adjust_public_access_block():
    """Adjust Public Access Block to allow presigned URLs."""
    print("\n" + "="*60)
    print("STEP 2: Adjusting Public Access Block settings")
    print("="*60)

    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
            region_name=Config.AWS_REGION,
            endpoint_url=f'https://s3.{Config.AWS_REGION}.amazonaws.com'
        )

        # New configuration that allows presigned URLs
        new_config = {
            'BlockPublicAcls': True,        # Keep blocking public ACLs (security)
            'IgnorePublicAcls': True,       # Keep ignoring public ACLs (security)
            'BlockPublicPolicy': False,     # ⚠️ Allow bucket policies to work
            'RestrictPublicBuckets': False  # ⚠️ Allow presigned URL access
        }

        print("📋 New Public Access Block configuration:")
        print(f"   BlockPublicAcls: {new_config['BlockPublicAcls']}")
        print(f"   IgnorePublicAcls: {new_config['IgnorePublicAcls']}")
        print(f"   BlockPublicPolicy: {new_config['BlockPublicPolicy']} ⬅ CHANGED")
        print(f"   RestrictPublicBuckets: {new_config['RestrictPublicBuckets']} ⬅ CHANGED")
        print()

        print("🔄 Applying new configuration...")
        s3_client.put_public_access_block(
            Bucket=Config.S3_VIDEO_BUCKET,
            PublicAccessBlockConfiguration=new_config
        )

        print()
        print("✅ Public Access Block configuration updated!")
        print()
        print("Changes made:")
        print("   BlockPublicPolicy: False")
        print("     → Allows bucket policies to work")
        print("   RestrictPublicBuckets: False")
        print("     → Allows presigned URL access from external services")
        print()
        print("Security maintained:")
        print("   ✅ Public ACLs still blocked")
        print("   ✅ Presigned URLs still require signature validation")
        print("   ✅ URLs expire after 24 hours")
        print("   ✅ Backend controls URL generation (JWT auth)")
        print()

        return True

    except ClientError as e:
        print(f"❌ Error adjusting Public Access Block: {e}")
        print()
        print("Common issues:")
        print("1. Insufficient IAM permissions (need s3:PutBucketPublicAccessBlock)")
        print("2. Account-level restrictions preventing changes")
        print()
        print("Alternative: Adjust settings manually via AWS Console:")
        print(f"1. Go to AWS S3 Console → {Config.S3_VIDEO_BUCKET}")
        print("2. Navigate to 'Permissions' tab")
        print("3. Scroll to 'Block public access' section")
        print("4. Click 'Edit'")
        print("5. Uncheck 'Block public and cross-account access to buckets...")
        print("6. Uncheck 'Block public and cross-account access if bucket...")
        print("7. Save changes")
        print()
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def verify_public_access_block():
    """Verify the Public Access Block was adjusted correctly."""
    print("\n" + "="*60)
    print("STEP 3: Verifying Public Access Block settings")
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

        print("✅ Updated Public Access Block configuration:")
        print(f"   BlockPublicAcls: {config.get('BlockPublicAcls', False)}")
        print(f"   IgnorePublicAcls: {config.get('IgnorePublicAcls', False)}")
        print(f"   BlockPublicPolicy: {config.get('BlockPublicPolicy', False)}")
        print(f"   RestrictPublicBuckets: {config.get('RestrictPublicBuckets', False)}")
        print()

        # Verify expected settings
        block_policy = config.get('BlockPublicPolicy', True)
        restrict_buckets = config.get('RestrictPublicBuckets', True)

        if not block_policy and not restrict_buckets:
            print("✅ Configuration verified correctly")
            print("   Presigned URLs should now work")
            return True
        else:
            print("⚠️  Configuration may not be correct")
            print(f"   BlockPublicPolicy: {block_policy} (expected: False)")
            print(f"   RestrictPublicBuckets: {restrict_buckets} (expected: False)")
            return False

    except ClientError as e:
        print(f"❌ Error verifying Public Access Block: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def restore_default_settings():
    """Helper function to restore default (strict) settings if needed."""
    print("\n" + "="*60)
    print("OPTIONAL: Restore Default Settings")
    print("="*60)
    print("If you need to revert to strict security settings, run:")
    print()
    print("import boto3")
    print("from config import Config")
    print()
    print("s3_client = boto3.client('s3',")
    print("    aws_access_key_id=Config.AWS_ACCESS_KEY_ID,")
    print("    aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,")
    print("    region_name=Config.AWS_REGION,")
    print("    endpoint_url=f'https://s3.{Config.AWS_REGION}.amazonaws.com'")
    print(")")
    print()
    print("s3_client.put_public_access_block(")
    print(f"    Bucket='{Config.S3_VIDEO_BUCKET}',")
    print("    PublicAccessBlockConfiguration={")
    print("        'BlockPublicAcls': True,")
    print("        'IgnorePublicAcls': True,")
    print("        'BlockPublicPolicy': True,      # Restore")
    print("        'RestrictPublicBuckets': True   # Restore")
    print("    }")
    print(")")
    print()


def main():
    """Main adjustment workflow."""
    print("\n" + "="*60)
    print("ADJUST PUBLIC ACCESS BLOCK FOR PRESIGNED URL ACCESS")
    print("="*60)
    print("This script adjusts S3 Public Access Block settings to allow")
    print("presigned URLs to work with external services like Replicate.")
    print()
    print(f"Bucket: {Config.S3_VIDEO_BUCKET}")
    print(f"Region: {Config.AWS_REGION}")
    print()
    print("⚠️  This is a fallback approach. If possible, use:")
    print("   python setup_s3_bucket_policy.py")
    print("   (More granular control via bucket policy)")
    print()

    # Step 1: Check current settings
    current_config = get_current_public_access_block()

    # If settings already allow presigned URLs, no need to change
    if current_config:
        if not current_config.get('BlockPublicPolicy', False) and \
           not current_config.get('RestrictPublicBuckets', False):
            print("\n" + "="*60)
            print("✅ Public Access Block already configured correctly")
            print("="*60)
            print("Presigned URLs should already work.")
            print()
            print("Next steps:")
            print("1. Run: python test_presigned_access.py")
            print("2. Test video processing with Replicate")
            print()
            return

    # Step 2: Adjust settings
    adjusted = adjust_public_access_block()
    if not adjusted:
        print("\n" + "="*60)
        print("❌ ADJUSTMENT FAILED")
        print("="*60)
        print("Please adjust settings manually via AWS Console")
        print("See error message above for instructions")
        print()
        return

    # Step 3: Verify settings
    verified = verify_public_access_block()
    if not verified:
        print("\n⚠️  Settings verification failed")
        print("   Check AWS Console to confirm settings are correct")

    # Show restore instructions
    restore_default_settings()

    # Final summary
    print("\n" + "="*60)
    print("ADJUSTMENT SUMMARY")
    print("="*60)

    if adjusted and verified:
        print("✅ Public Access Block: ADJUSTED")
        print("✅ Settings verification: PASSED")
        print()
        print("🎉 Adjustment complete! Presigned URLs should now work.")
        print()
        print("Next steps:")
        print("1. Run: python test_presigned_access.py")
        print("   (Verify presigned URLs work)")
        print("2. Test video processing with Replicate")
        print("3. Monitor Replicate predictions for success")
    else:
        print("❌ Public Access Block: FAILED")
        print()
        print("Required action:")
        print("1. Adjust settings manually via AWS Console")
        print("2. Run: python test_presigned_access.py")

    print("="*60 + "\n")


if __name__ == "__main__":
    main()
