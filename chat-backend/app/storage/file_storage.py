import boto3
from botocore.exceptions import ClientError
import os
from werkzeug.utils import secure_filename
from ..config import S3_BUCKET

class FileStorage:
    def __init__(self):
        self.s3 = boto3.client('s3')  # Uses default credential chain
        self.bucket = S3_BUCKET

    def save_file(self, file, max_size: int) -> str:
        if not file.filename:
            raise ValueError("No file provided")
            
        # Check file size
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)
        
        if size > max_size:
            raise ValueError(f"File too large. Maximum size is {max_size/1024/1024}MB")

        filename = secure_filename(file.filename)
        unique_filename = f"{os.urandom(4).hex()}{os.path.splitext(filename)[1]}"
        
        try:
            self.s3.upload_fileobj(file, self.bucket, unique_filename)
            return unique_filename
        except ClientError as e:
            raise ValueError(f"Failed to upload file: {str(e)}")

    def delete_file(self, filename: str) -> None:
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=filename)
        except ClientError as e:
            raise ValueError(f"Failed to delete file: {str(e)}")

    def get_file_url(self, filename: str) -> str:
        try:
            url = self.s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': filename},
                ExpiresIn=3600  # URL expires in 1 hour
            )
            return url
        except ClientError as e:
            raise ValueError(f"Failed to generate URL: {str(e)}") 