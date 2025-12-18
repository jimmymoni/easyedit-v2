import boto3
from config import Config

s3 = boto3.client(
    's3',
    aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY
)

try:
    location = s3.get_bucket_location(Bucket=Config.S3_VIDEO_BUCKET)
    region = location['LocationConstraint'] or 'us-east-1'
    print(f"Bucket: {Config.S3_VIDEO_BUCKET}")
    print(f"Region: {region}")
except Exception as e:
    print(f"Error: {e}")
