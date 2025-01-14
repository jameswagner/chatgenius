import boto3
from botocore.exceptions import ClientError
import os
from werkzeug.utils import secure_filename

class FileStorage:
    def __init__(self):
        print("\n=== Initializing FileStorage ===")
        self.s3 = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION')
        )
        self.bucket_name = os.environ.get('S3_BUCKET_NAME', 'chatgenius-jrw')
        print(f"Using bucket: {self.bucket_name}")

    def save_file(self, file, filename):
        print(f"\n=== Saving file: {filename} ===")
        try:
            print("Attempting S3 upload...")
            self.s3.upload_fileobj(file, self.bucket_name, filename)
            print("Upload successful")
            return True
        except Exception as e:
            print(f"Upload failed: {str(e)}")
            print(f"Error type: {type(e)}")
            return False

    def get_file_url(self, filename: str) -> str:
        try:
            url = self.s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': filename
                },
                ExpiresIn=3600
            )
            return url
        except Exception as e:
            print(f"Failed to generate URL: {str(e)}")
            print(f"Error type: {type(e)}")
            raise ValueError(f"File {filename} not found") 