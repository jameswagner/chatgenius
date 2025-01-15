from typing import Optional, List, Tuple
from datetime import datetime
from .base_service import BaseService
from ..models.workspace import Workspace
import boto3
import os
from boto3.dynamodb.conditions import Key

class WorkspaceService(BaseService):
    def __init__(self, table_name: str = None):
        super().__init__(table_name)
        self.dynamodb = boto3.resource(
            'dynamodb',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION')
        )

    def create_workspace(self, name: str) -> Workspace:
        """Create a new workspace."""
        workspace_id = self._generate_id()
        timestamp = self._now()
        item = {
            'PK': f'WORKSPACE#{workspace_id}',
            'SK': '#METADATA',
            'id': workspace_id,
            'name': name,
            'created_at': timestamp,
            'entity_type': 'WORKSPACE'
        }
        self.table.put_item(Item=item)
        return Workspace(id=workspace_id, name=name, created_at=timestamp)

    def get_workspace_by_id(self, workspace_id: str) -> Optional[Workspace]:
        """Get a workspace by its ID."""
        response = self.table.get_item(
            Key={
                'PK': f'WORKSPACE#{workspace_id}',
                'SK': '#METADATA'
            }
        )
        if 'Item' not in response:
            return None
        item = response['Item']
        return Workspace(id=item['id'], name=item['name'], created_at=item['created_at']) 

    def get_all_workspaces(self) -> List[Workspace]:
        """Get all unique workspaces using the entity_type index, handling pagination internally."""
        unique_workspaces = {}
        last_evaluated_key = None
        while True:
            query_params = {
                'IndexName': 'entity_type',
                'KeyConditionExpression': Key('entity_type').eq('WORKSPACE')
            }
            if last_evaluated_key:
                query_params['ExclusiveStartKey'] = last_evaluated_key

            response = self.table.query(**query_params)
            
            for item in response.get('Items', []):
                workspace_id = item['id']
                if workspace_id not in unique_workspaces:
                    unique_workspaces[workspace_id] = Workspace(id=workspace_id, name=item['name'], created_at=item['created_at'])
            
            last_evaluated_key = response.get('LastEvaluatedKey')
            if not last_evaluated_key:
                break
        return list(unique_workspaces.values()) 