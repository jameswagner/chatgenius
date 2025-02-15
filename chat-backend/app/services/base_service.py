import boto3
import os
import uuid
from datetime import datetime, timezone
from typing import Dict

class BaseService:
    def __init__(self, table_name=None):
        """Initialize DynamoDB resource and table."""
        self.dynamodb = boto3.resource(
            'dynamodb',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION')
        )
        self.table = self.dynamodb.Table(table_name or os.environ.get('DYNAMODB_TABLE', 'chat_app_jrw'))
        
    def _generate_id(self) -> str:
        """Generate a unique ID."""
        return str(uuid.uuid4())
        
    def _now(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat()
        
    def _clean_item(self, item: Dict) -> Dict:
        """Remove DynamoDB-specific fields from an item."""
        cleaned = item.copy()
        # Remove DynamoDB-specific fields
        for field in ['PK', 'SK', 'GSI1PK', 'GSI1SK', 'GSI2PK', 'GSI2SK', 'GSI3PK', 'GSI3SK', 'GSI4PK', 'GSI4SK']:
            cleaned.pop(field, None)
        return cleaned 