from __future__ import annotations
from typing import Optional, List, Tuple
from datetime import datetime
from .base_service import BaseService
from ..models.workspace import Workspace
import boto3
import os
from boto3.dynamodb.conditions import Key
from uuid import uuid4
from ..models.user import User

# WorkspaceService Schema:
# - Primary Key (PK): WORKSPACE#{workspace_id}
# - Sort Key (SK): MEMBER#{user_id} or #METADATA for workspace metadata
# - GSI2PK: WORKSPACE_NAME#{name} for querying by workspace name
# - GSI2SK: #METADATA for workspace metadata
# - GSI5PK: USER#{user_id} for querying workspaces by user
# - GSI5SK: WORKSPACE#{workspace_id} for querying users by workspace
# This schema allows efficient lookup of:
#   - Users given a workspace
#   - Workspaces given a user
#   - Workspaces by name
#   - Metadata retrieval for workspaces

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

    def get_all_workspaces(self, user_id: str = None) -> List[Workspace]:
        """Get all unique workspaces using the entity_type index, handling pagination internally."""
        from .channel_service import ChannelService  # Local import to avoid circular dependency
        channel_service = ChannelService()
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
                # if user_id is not None, check if the user is a member of at least one channel in the workspace
                if user_id:
                    channels = channel_service.get_workspace_channels(workspace_id, user_id)
                    # if channel.is_member is true for any channel in the workspace, add the workspace to the unique_workspaces dictionary
                    if any(channel.is_member for channel in channels):
                        unique_workspaces[workspace_id] = Workspace(id=workspace_id, name=item['name'], created_at=item['created_at'])
                elif workspace_id not in unique_workspaces:
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

    def get_users_by_workspace(self, workspace_id: str) -> List[User]:
        """Get all users who are members of at least one channel in the workspace."""
        from .channel_service import ChannelService  # Local import to avoid circular dependency
        from .user_service import UserService

        channel_service = ChannelService()
        user_service = UserService()

        # Get all channels in the workspace
        channels = channel_service.get_workspace_channels(workspace_id)

        # Collect all unique user IDs from these channels
        user_ids = set()
        for channel in channels:
            members = channel_service.get_channel_members(channel.id)
            user_ids.update(member['id'] for member in members)

        # Retrieve user details based on these IDs
        users = user_service.get_users_by_ids(list(user_ids))

        return users 

    def add_user_to_workspace(self, workspace_id: str, user_id: str):
        # Add a user to a workspace
        item = {
            'PK': f'WORKSPACE#{workspace_id}',
            'SK': f'MEMBER#{user_id}',
            'GSI5PK': f'USER#{user_id}',
            'GSI5SK': f'WORKSPACE#{workspace_id}'
        }
        self.dynamodb.put_item(Item=item)

    def get_workspaces_by_user(self, user_id: str) -> List[str]:
        # Retrieve all workspaces a user is a member of
        response = self.table.query(
            KeyConditionExpression=Key('PK').eq(f'WORKSPACE#{user_id}')
        )
        return [item['SK'].split('#')[1] for item in response['Items']]
