from typing import Optional, List, Tuple
from datetime import datetime
from .base_service import BaseService
from ..models.workspace import Workspace
import boto3
import os
from boto3.dynamodb.conditions import Key
from uuid import uuid4

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
        workspace_id = str(uuid4())
        timestamp = datetime.utcnow().isoformat()
        self.table.put_item(
            Item={
                'PK': f'WORKSPACE#{workspace_id}',
                'SK': '#METADATA',
                'GSI2PK': f'WORKSPACE_NAME#{name}',
                'GSI2SK': '#METADATA',
                'name': name,
                'created_at': timestamp,
                'entity_type': 'WORKSPACE',
                'id': workspace_id
            }
        )
        # Verify that the item was stored
        response = self.table.get_item(
            Key={
                'PK': f'WORKSPACE#{workspace_id}',
                'SK': '#METADATA'
            }
        )
        if 'Item' in response:
            print("Stored Workspace Item:", response['Item'])
        else:
            print("Workspace item not found after creation.")
        return Workspace(id=workspace_id, name=name, created_at=timestamp, entity_type='WORKSPACE')

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

    def get_workspace_name_by_id(self, workspace_id: str) -> Optional[str]:
        """Get the workspace name by its ID."""
        workspace = self.get_workspace_by_id(workspace_id)
        print(f"Workspace name: {workspace.name}")
        return workspace.name if workspace else None 

    def get_workspace_by_name(self, name: str) -> Optional[Workspace]:
        """Get a workspace by its name using GSI2PK."""
        print(f"Querying GSI2 for workspace name: {name}")
        response = self.table.query(
            IndexName='GSI2',
            KeyConditionExpression=Key('GSI2PK').eq(f'WORKSPACE_NAME#{name}')
        )
        print(f"Query response: {response}")
        if 'Items' not in response or not response['Items']:
            print("No items found for the given workspace name.")
            return None
        item = response['Items'][0]
        print(f"Found workspace item: {item}")
        return Workspace(id=item['id'], name=item['name'], created_at=item['created_at']) 