"""User service for managing users in DynamoDB

Schema for Users:
    PK=USER#{id} SK=#METADATA
    GSI1PK=TYPE#{type} GSI1SK=NAME#{name}  # For listing users by type
    GSI2PK=EMAIL#{email} GSI2SK=#METADATA  # For email uniqueness and lookup
    GSI4PK=NAME#{name} GSI4SK=#METADATA  # For username uniqueness and lookup
"""

from typing import Optional, List, Dict, Set
from boto3.dynamodb.conditions import Key, Attr
from app.models.user import User
from .base_service import BaseService

class UserService(BaseService):
    def create_user(self, email: str, name: str, password: str = None, type: str = 'user', role: str = None, bio: str = None, id: str = None) -> User:
        """Create a new user
        
        Args:
            email: User's email address
            name: User's display name
            password: User's password (optional for persona users)
            type: User type ('user' or 'persona')
            role: User's role (for persona users)
            bio: User's bio (for persona users)
            id: Optional user ID
        """
        # Check if user exists using GSI2 (email)
        response = self.table.query(
            IndexName='GSI2',
            KeyConditionExpression=Key('GSI2PK').eq(f'EMAIL#{email}')
        )
        if response['Items']:
            raise ValueError("User already exists with this email")
            
        # Check if username is taken using GSI4
        response = self.table.query(
            IndexName='GSI4',
            KeyConditionExpression=Key('GSI4PK').eq(f'NAME#{name}')
        )
        if response['Items']:
            raise ValueError("Username is already taken")
            
        # Validate persona fields
        if type == 'persona':
            if not role:
                raise ValueError("Role is required for persona users")
            if password:
                print("Warning: Password provided for persona user will be ignored")
                password = None
        
        user_id = id or self._generate_id()
        timestamp = self._now()
        
        item = {
            'PK': f'USER#{user_id}',
            'SK': '#METADATA',
            'GSI1PK': f'TYPE#{type}',
            'GSI1SK': f'NAME#{name}',
            'GSI2PK': f'EMAIL#{email}',
            'GSI2SK': '#METADATA',
            'GSI4PK': f'NAME#{name}',
            'GSI4SK': '#METADATA',
            'id': user_id,
            'email': email,
            'name': name,
            'password': password,
            'type': type,
            'status': 'online',
            'last_active': timestamp,
            'created_at': timestamp,
            'role': role,
            'bio': bio
        }
        
        try:
            self.table.put_item(Item=item)
            return User(**self._clean_item(item))
        except Exception as e:
            print(f"Error creating user {name}: {str(e)}")
            raise e

    def get_user_by_name(self, name: str) -> Optional[User]:
        """Get a user by their username."""
        print(f"\n=== Getting user by name: {name} ===")
        try:
            response = self.table.query(
                IndexName='GSI4',
                KeyConditionExpression=Key('GSI4PK').eq(f'NAME#{name}')
            )
            
            if response['Items']:
                item = response['Items'][0]
                print(f"Found user: {item['name']} (id: {item['id']})")
                return User(**self._clean_item(item))
            print("No user found with this username")
            return None
        except Exception as e:
            print(f"Error getting user by name: {str(e)}")
            raise

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get a user by their email address."""
        print(f"\n=== Getting user by email: {email} ===")
        try:
            response = self.table.query(
                IndexName='GSI2',
                KeyConditionExpression=Key('GSI2PK').eq(f'EMAIL#{email}')
            )
            
            if response['Items']:
                item = response['Items'][0]
                print(f"Found user: {item['name']} (id: {item['id']})")
                return User(**self._clean_item(item))
            print("No user found with this email")
            return None
        except Exception as e:
            print(f"Error getting user by email: {str(e)}")
            raise

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get a user by their ID."""
        try:
            response = self.table.get_item(
                Key={
                    'PK': f'USER#{user_id}',
                    'SK': '#METADATA'
                }
            )
            
            if 'Item' not in response:
                print(f"No user found with ID: {user_id}")
                return None
                
            item = response['Item']
            return User(**self._clean_item(item))
        except Exception as e:
            print(f"Error getting user by ID: {str(e)}")
            print(f"Error type: {type(e)}")
            raise

    def update_user_status(self, user_id: str, status: str) -> Optional[User]:
        """Update a user's online status."""
        timestamp = self._now()
        
        # Update user status without modifying GSI1PK
        self.table.update_item(
            Key={
                'PK': f'USER#{user_id}',
                'SK': '#METADATA'
            },
            UpdateExpression='SET #status = :status, #last_active = :ts',
            ExpressionAttributeNames={
                '#status': 'status',
                '#last_active': 'last_active'
            },
            ExpressionAttributeValues={
                ':status': status,
                ':ts': timestamp
            }
        )
        
        return self.get_user_by_id(user_id)

    def get_all_users(self) -> List[Dict]:
        """Get all users"""
        response = self.table.query(
            IndexName='GSI1',
            KeyConditionExpression=Key('GSI1PK').eq('TYPE#user')
        )
        
        users = []
        for item in response.get('Items', []):
            cleaned = self._clean_item(item)
            users.append({
                'id': cleaned['id'],
                'name': cleaned['name'],
                'email': cleaned['email']
            })
            
        return users

    def get_persona_users(self) -> List[User]:
        """Get all persona users."""
        response = self.table.query(
            IndexName='GSI1',
            KeyConditionExpression=Key('GSI1PK').eq('TYPE#persona')
        )
        
        return [User(**self._clean_item(item)) for item in response['Items']]

    def _batch_get_users(self, user_ids: Set[str]) -> List[User]:
        """Batch get multiple users by their IDs."""
        if not user_ids:
            return []
            
        # DynamoDB batch_get_item has a limit of 100 items
        users = []
        for chunk in [list(user_ids)[i:i + 100] for i in range(0, len(user_ids), 100)]:
            request_items = {
                self.table.name: {
                    'Keys': [{'PK': f'USER#{user_id}', 'SK': '#METADATA'} for user_id in chunk],
                    'ConsistentRead': False
                }
            }
            response = self.dynamodb.batch_get_item(RequestItems=request_items)
            
            for item in response['Responses'][self.table.name]:
                users.append(User(**self._clean_item(item)))
                
        return users 