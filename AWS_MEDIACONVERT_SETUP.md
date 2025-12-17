# AWS MediaConvert Setup Guide

This guide walks you through setting up AWS MediaConvert for cloud-based video transcoding in EasyEdit v2.

## Prerequisites

- AWS account with billing enabled
- AWS CLI installed and configured
- Existing S3 bucket (`easyedit-videos` or your configured bucket)

## Step 1: Create IAM Role for MediaConvert

AWS MediaConvert needs an IAM role to access your S3 bucket for input/output files.

### Option A: Using AWS Console (Recommended for Beginners)

1. Go to [AWS IAM Console](https://console.aws.amazon.com/iam/)
2. Click **Roles** → **Create role**
3. Select **AWS service** → **MediaConvert**
4. Click **Next: Permissions**
5. Attach these policies:
   - `AmazonS3FullAccess` (or create custom policy with just your bucket)
   - `AWSElementalMediaConvertFullAccess`
6. Click **Next: Tags** (skip tags)
7. Click **Next: Review**
8. Role name: `EasyEditMediaConvertRole`
9. Click **Create role**
10. Copy the **Role ARN** (e.g., `arn:aws:iam::123456789012:role/EasyEditMediaConvertRole`)

### Option B: Using AWS CLI (Faster)

```bash
# 1. Create trust policy file
cat > mediaconvert-trust-policy.json <<EOF
{
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
EOF

# 2. Create the IAM role
aws iam create-role \
  --role-name EasyEditMediaConvertRole \
  --assume-role-policy-document file://mediaconvert-trust-policy.json

# 3. Attach S3 access policy
aws iam attach-role-policy \
  --role-name EasyEditMediaConvertRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

# 4. Attach MediaConvert policy
aws iam attach-role-policy \
  --role-name EasyEditMediaConvertRole \
  --policy-arn arn:aws:iam::aws:policy/AWSElementalMediaConvertFullAccess

# 5. Get the role ARN
aws iam get-role --role-name EasyEditMediaConvertRole \
  | grep Arn
```

### Option C: Custom S3 Policy (Production - Most Secure)

For production, create a custom policy that grants access only to your specific bucket:

```json
{
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
        "arn:aws:s3:::easyedit-videos",
        "arn:aws:s3:::easyedit-videos/*"
      ]
    }
  ]
}
```

Save as `s3-bucket-policy.json` and attach:

```bash
aws iam put-role-policy \
  --role-name EasyEditMediaConvertRole \
  --policy-name EasyEditS3Access \
  --policy-document file://s3-bucket-policy.json
```

## Step 2: Update Environment Variables

Add the following to `backend/.env`:

```bash
# AWS MediaConvert Configuration
AWS_MEDIACONVERT_ROLE_ARN=arn:aws:iam::YOUR_ACCOUNT_ID:role/EasyEditMediaConvertRole

# Optional: Manually set endpoint (auto-discovered if not set)
# AWS_MEDIACONVERT_ENDPOINT=https://abc123def.mediaconvert.us-east-1.amazonaws.com

# Optional: Queue name (defaults to "Default")
# AWS_MEDIACONVERT_QUEUE=Default
```

**Replace** `YOUR_ACCOUNT_ID` with your actual AWS account ID (visible in IAM role ARN).

## Step 3: Verify AWS Credentials

Ensure your AWS credentials are set in `backend/.env`:

```bash
# AWS S3 Credentials (already configured for S3 uploads)
AWS_ACCESS_KEY_ID=your_aws_access_key_here
AWS_SECRET_ACCESS_KEY=your_aws_secret_key_here
AWS_REGION=us-east-1
S3_VIDEO_BUCKET=easyedit-videos
```

## Step 4: Test MediaConvert Setup

Run the test script to verify everything is configured correctly:

```bash
cd backend
python test_hybrid_video_processing.py
```

Expected output:
```
============================================================
🚀 HYBRID CLOUD VIDEO PROCESSING TEST SUITE
   AWS MediaConvert + Replicate Integration
============================================================

============================================================
TEST 1: Configuration Verification
============================================================
✅ AWS_ACCESS_KEY_ID: AKIAIOSFOD...
✅ AWS_SECRET_ACCESS_KEY: wJalrXUtnF...
✅ AWS_REGION: us-east-1
✅ S3_VIDEO_BUCKET: easyedit-videos
✅ AWS_MEDIACONVERT_ROLE_ARN: arn:aws:iam::12345...
✅ REPLICATE_API_TOKEN: r8_JIkSpRrjAY9RRp...

✅ All configuration verified!

============================================================
TEST 2: Processor Initialization
============================================================
✅ ReplicateVideoProcessor initialized successfully
   AWS MediaConvert endpoint: https://abc123.mediaconvert.us-east-1.amazonaws.com
   Replicate audio model: lucataco/extract-audio
   Replicate merge model: foixasoftware/ffmpeg
```

## Step 5: Upload Test Video (Optional)

To test full transcoding, upload a small test video to S3:

```bash
# Upload a test video
aws s3 cp your-test-video.mp4 s3://easyedit-videos/test/sample.mp4

# Verify upload
aws s3 ls s3://easyedit-videos/test/
```

Then run the test script and select `y` when prompted to test MediaConvert transcoding.

## Troubleshooting

### Error: "Role ARN is invalid"

**Cause**: IAM role doesn't exist or ARN is malformed

**Solution**:
```bash
# Verify role exists
aws iam get-role --role-name EasyEditMediaConvertRole

# Copy the ARN from output
```

### Error: "Access Denied"

**Cause**: IAM role doesn't have S3 permissions

**Solution**:
```bash
# Re-attach S3 policy
aws iam attach-role-policy \
  --role-name EasyEditMediaConvertRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
```

### Error: "MediaConvert endpoint not found"

**Cause**: MediaConvert not available in your region

**Solution**:
- MediaConvert is available in most regions
- Check: https://aws.amazon.com/about-aws/global-infrastructure/regional-product-services/
- Try region `us-east-1` or `us-west-2`

### Error: "Insufficient permissions"

**Cause**: AWS credentials don't have IAM permissions

**Solution**:
- Use AWS account root user temporarily
- OR grant IAM permissions to create/manage roles:
  ```json
  {
    "Effect": "Allow",
    "Action": [
      "iam:CreateRole",
      "iam:AttachRolePolicy",
      "iam:GetRole"
    ],
    "Resource": "*"
  }
  ```

## Cost Estimation

AWS MediaConvert pricing (as of 2025):

| Video Length | Resolution | Preset | Estimated Cost |
|--------------|------------|--------|----------------|
| 5 minutes    | 720p       | GOOD   | ~$0.04         |
| 30 minutes   | 1080p      | GOOD   | ~$0.23         |
| 2 hours      | 1080p      | GOOD   | ~$0.90         |
| 2 hours      | 1080p      | BEST   | ~$1.35         |

**Pricing Details**:
- Basic tier: $0.0075 per minute
- Professional tier: $0.0120 per minute
- Presets:
  - GOOD = Single-pass encoding (fastest, cheapest)
  - BETTER = Single-pass HQ (balanced)
  - BEST = Multi-pass HQ (slowest, highest quality)

For production YouTube videos (2-hour talking head at 1080p):
- **Cost**: ~$0.90/video using GOOD preset
- **Time**: ~10-15 minutes transcoding
- **Output**: Web-optimized H.264/AAC MP4

## Next Steps

1. ✅ IAM role created
2. ✅ Environment variables configured
3. ✅ Test script passed
4. 🔄 **Integrate with upload flow** - Connect to background processor
5. 🔄 **Test full workflow** - Upload → Transcode → Extract audio → Whisper → Timeline
6. 🔄 **Monitor costs** - Check AWS billing dashboard

## Additional Resources

- [AWS MediaConvert Documentation](https://docs.aws.amazon.com/mediaconvert/)
- [AWS MediaConvert Pricing](https://aws.amazon.com/mediaconvert/pricing/)
- [Boto3 MediaConvert API Reference](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/mediaconvert.html)
- [IAM Roles Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)

## Support

If you encounter issues:

1. Check AWS CloudWatch logs: https://console.aws.amazon.com/cloudwatch/
2. Review MediaConvert job errors: https://console.aws.amazon.com/mediaconvert/
3. Verify S3 bucket permissions
4. Check backend logs: `backend/logs/app.log`

---

**Architecture Note**: This hybrid approach uses AWS MediaConvert for heavy video transcoding (GPU-accelerated, production-grade) while using Replicate for lightweight utilities (audio extraction, video merging) to balance cost and performance.
