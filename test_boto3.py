import os

from dotenv import load_dotenv

load_dotenv()

AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME')

print(AWS_ACCESS_KEY_ID)
print(AWS_SECRET_ACCESS_KEY)
print(AWS_STORAGE_BUCKET_NAME)
print(AWS_S3_REGION_NAME)

import boto3

bucket_name = AWS_STORAGE_BUCKET_NAME

s3 = boto3.client('s3')

try:
    response = s3.list_objects_v2(Bucket=bucket_name)
    print("S3 access successful! Contents of the bucket:")
    if 'Contents' in response:
        for obj in response['Contents']:
            print(obj['Key'])
    else:
        print("Bucket is empty.")
except Exception as e:
    print("Error accessing S3:", e)


bucket_name = AWS_STORAGE_BUCKET_NAME
file_path = 'test_upload.txt'

# Create a test file
with open(file_path, 'w') as f:
    f.write('Hello, S3!')

s3 = boto3.client('s3')
try:
    s3.upload_file(file_path, bucket_name, 'test_upload.txt')
    print("Upload successful!")
except Exception as e:
    print("Upload failed:", e)