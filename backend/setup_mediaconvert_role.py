"""
Setup AWS MediaConvert IAM Role using boto3

This script creates the necessary IAM role for AWS MediaConvert to access your S3 bucket.
"""

import boto3
import json
from config import Config

def create_mediaconvert_role():
    """Create IAM role for AWS MediaConvert"""

    print("Creating AWS MediaConvert IAM Role...")
    print(f"Region: {Config.AWS_REGION}")
    print(f"Bucket: {Config.S3_VIDEO_BUCKET}")

    # Create IAM client
    iam = boto3.client(
        'iam',
        region_name=Config.AWS_REGION,
        aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY
    )

    role_name = "EasyEditMediaConvertRole"

    # Trust policy for MediaConvert service
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "mediaconvert.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }

    # S3 access policy for your bucket
    s3_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:ListBucket"
                ],
                "Resource": [
                    f"arn:aws:s3:::{Config.S3_VIDEO_BUCKET}",
                    f"arn:aws:s3:::{Config.S3_VIDEO_BUCKET}/*"
                ]
            }
        ]
    }

    try:
        # Step 1: Create the role
        print("\nStep 1: Creating IAM role...")
        role = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Role for AWS MediaConvert to access S3 bucket for EasyEdit video processing"
        )

        role_arn = role['Role']['Arn']
        print(f"   SUCCESS: Role created: {role_arn}")

        # Step 2: Attach S3 inline policy
        print("\nStep 2: Attaching S3 access policy...")
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName="EasyEditS3Access",
            PolicyDocument=json.dumps(s3_policy)
        )
        print("   SUCCESS: S3 policy attached")

        # Step 3: Display .env configuration
        print("\n" + "="*60)
        print("SUCCESS! IAM Role Created")
        print("="*60)
        print("\nAdd this to backend/.env:")
        print(f"\nAWS_MEDIACONVERT_ROLE_ARN={role_arn}")
        print("\n" + "="*60)

        return role_arn

    except iam.exceptions.EntityAlreadyExistsException:
        print(f"\nRole '{role_name}' already exists!")

        # Get existing role ARN
        role = iam.get_role(RoleName=role_name)
        role_arn = role['Role']['Arn']

        print(f"Existing role ARN: {role_arn}")
        print("\nAdd this to backend/.env:")
        print(f"\nAWS_MEDIACONVERT_ROLE_ARN={role_arn}")

        return role_arn

    except Exception as e:
        print(f"\nERROR: Failed to create role: {e}")
        print("\nAlternative: Create role manually in AWS Console")
        print("See AWS_MEDIACONVERT_SETUP.md for instructions")
        raise

if __name__ == "__main__":
    try:
        role_arn = create_mediaconvert_role()
        print("\nNext step: Add the role ARN to backend/.env and run tests")
    except Exception as e:
        print(f"\nSetup failed: {e}")
        exit(1)
