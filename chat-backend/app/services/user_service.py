from typing import Optional, List, Dict, Set
from boto3.dynamodb.conditions import Key, Attr
from app.models.user import User
from .base_service import BaseService

class UserService(BaseService):
    def create_user(self, email: str, name: str, password: str, type: str = "user") -> User:
        """Create a new user."""
        print(f"\n=== Creating user: email={email}, name={name}, type={type} ===")
        user_id = self._generate_id()
        timestamp = self._now()
        
        try:
            item = {
                'PK': f'USER#{user_id}',
                'SK': '#METADATA',
                'GSI1PK': 'TYPE#user',
                'GSI1SK': f'EMAIL#{email}',
                'id': user_id,
                'email': email,
                'name': name,
                'password': password,
                'type': type,
                'created_at': timestamp,
                'status': 'online'
            }
            print(f"Attempting to create user with item: {item}")
            
            self.table.put_item(Item=item)
            print(f"User item created successfully with ID: {user_id}")
            
            return User(id=user_id, email=email, name=name, type=type, created_at=timestamp, status='online')
        except Exception as e:
            print(f"Error creating user: {str(e)}")
            print(f"Error type: {type(e)}")
            raise

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get a user by their email address."""
        print(f"\n=== Getting user by email: {email} ===")
        try:
            response = self.table.query(
                IndexName='GSI1',
                KeyConditionExpression=Key('GSI1PK').eq('TYPE#user') & Key('GSI1SK').eq(f'EMAIL#{email}')
            )
            
            if response['Items']:
                item = response['Items'][0]
                print(f"Found user: {item['name']} (id: {item['id']})")
                return User(
                    id=item['id'],
                    email=item['email'],
                    name=item['name'],
                    type=item['type'],
                    created_at=item['created_at'],
                    status=item.get('status', 'offline'),
                    password=item.get('password')
                )
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
        
        # Update user status
        self.table.update_item(
            Key={
                'PK': f'USER#{user_id}',
                'SK': '#METADATA'
            },
            UpdateExpression='SET #status = :status, #last_active = :ts, GSI1PK = :gsi1pk',
            ExpressionAttributeNames={
                '#status': 'status',
                '#last_active': 'last_active'
            },
            ExpressionAttributeValues={
                ':status': status,
                ':ts': timestamp,
                ':gsi1pk': f'STATUS#{status}'
            }
        )
        
        return self.get_user_by_id(user_id)

    def get_all_users(self) -> List[Dict]:
        """Get all users except password field."""
        response = self.table.scan(
            FilterExpression=Attr('type').eq('user')
        )
        
        # Clean items and only return necessary fields
        return [{
            'id': self._clean_item(item)['id'],
            'name': self._clean_item(item)['name']
        } for item in response['Items']]

    def get_persona_users(self) -> List[User]:
        """Get all persona users."""
        response = self.table.scan(
            FilterExpression=Attr('type').eq('persona')
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