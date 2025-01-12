import pytest
import boto3
from moto import mock_aws
from datetime import datetime, timezone
from app.services.message_service import MessageService
from app.services.user_service import UserService
from app.services.channel_service import ChannelService
from app.models.message import Message
from app.models.reaction import Reaction

@pytest.fixture
def aws_credentials():
    """Mocked AWS Credentials for moto"""
    import os
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

@pytest.fixture
def dynamodb(aws_credentials):
    """Create mock DynamoDB table"""
    with mock_aws():
        dynamodb = boto3.resource('dynamodb')
        
        # Create mock table with indexes
        table = dynamodb.create_table(
            TableName='test_table',
            KeySchema=[
                {'AttributeName': 'PK', 'KeyType': 'HASH'},
                {'AttributeName': 'SK', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'PK', 'AttributeType': 'S'},
                {'AttributeName': 'SK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI1PK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI1SK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI2PK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI2SK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI3PK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI3SK', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'GSI1',
                    'KeySchema': [
                        {'AttributeName': 'GSI1PK', 'KeyType': 'HASH'},
                        {'AttributeName': 'GSI1SK', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                },
                {
                    'IndexName': 'GSI2',
                    'KeySchema': [
                        {'AttributeName': 'GSI2PK', 'KeyType': 'HASH'},
                        {'AttributeName': 'GSI2SK', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                },
                {
                    'IndexName': 'GSI3',
                    'KeySchema': [
                        {'AttributeName': 'GSI3PK', 'KeyType': 'HASH'},
                        {'AttributeName': 'GSI3SK', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                }
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )
        
        yield table

@pytest.fixture
def message_service(dynamodb):
    return MessageService('test_table')

@pytest.fixture
def user_service(dynamodb):
    return UserService('test_table')

@pytest.fixture
def channel_service(dynamodb):
    return ChannelService('test_table')

def create_test_user(user_service, user_id="user1", name="Test User"):
    """Helper to create a test user"""
    email = f"{user_id}@test.com"
    return user_service.create_user(email=email, name=name, password="password", type="user", id=user_id)

def create_test_channel(channel_service, created_by="user1", name="test-channel"):
    """Create a test channel"""
    return channel_service.create_channel(name=name, type="public", created_by=created_by)

def test_create_message(message_service, user_service, channel_service):
    """Test creating a new message"""
    # Create test user and channel
    user = create_test_user(user_service)
    channel = create_test_channel(channel_service)
    
    # Create message
    content = "Hello, world!"
    message = message_service.create_message(
        channel_id=channel.id,
        user_id=user.id,
        content=content
    )
    
    # Verify message
    assert message.id is not None
    assert message.channel_id == channel.id
    assert message.user_id == user.id
    assert message.content == content
    assert message.created_at is not None
    assert message.user is not None
    assert message.user.name == user.name

def test_create_message_with_thread(message_service, user_service, channel_service):
    """Test creating a message in a thread"""
    user = create_test_user(user_service)
    channel = create_test_channel(channel_service)
    
    # Create parent message
    parent = message_service.create_message(
        channel_id=channel.id,
        user_id=user.id,
        content="Parent message"
    )
    
    # Create reply in thread
    reply = message_service.create_message(
        channel_id=channel.id,
        user_id=user.id,
        content="Reply message",
        thread_id=parent.id
    )
    
    assert reply.thread_id == parent.id

def test_get_message(message_service, user_service, channel_service):
    """Test retrieving a message by ID"""
    user = create_test_user(user_service)
    channel = create_test_channel(channel_service)
    
    # Create message
    message = message_service.create_message(
        channel_id=channel.id,
        user_id=user.id,
        content="Test message"
    )
    
    # Get message
    retrieved = message_service.get_message(message.id)
    assert retrieved is not None
    assert retrieved.id == message.id
    assert retrieved.content == message.content

def test_get_messages(message_service, user_service, channel_service):
    """Test retrieving messages from a channel"""
    user = create_test_user(user_service, "user1@test.com", "Test User")
    channel = create_test_channel(channel_service, user.id)
    
    # Create messages
    messages = []
    for i in range(3):
        message = message_service.create_message(
            channel_id=channel.id,
            user_id=user.id,
            content=f"Message {i}"
        )
        messages.append(message)
    
    # Get messages
    retrieved = message_service.get_messages(channel.id)
    assert len(retrieved) == 3
    for i, msg in enumerate(retrieved):
        assert msg.content == f"Message {i}"
        assert msg.user_id == user.id

def test_add_reaction(message_service, user_service, channel_service):
    """Test adding a reaction to a message"""
    user = create_test_user(user_service)
    channel = create_test_channel(channel_service)
    
    # Create message
    message = message_service.create_message(
        channel_id=channel.id,
        user_id=user.id,
        content="Test message"
    )
    
    # Add reaction
    reaction = message_service.add_reaction(
        message_id=message.id,
        user_id=user.id,
        emoji="👍"
    )
    
    assert reaction.message_id == message.id
    assert reaction.user_id == user.id
    assert reaction.emoji == "👍"
    
    # Verify reaction in message
    message = message_service.get_message(message.id)
    assert "👍" in message.reactions
    assert user.id in message.reactions["👍"]

def test_get_thread_messages(message_service, user_service, channel_service):
    """Test retrieving messages in a thread"""
    user = create_test_user(user_service)
    channel = create_test_channel(channel_service)
    
    # Create parent message
    parent = message_service.create_message(
        channel_id=channel.id,
        user_id=user.id,
        content="Parent message"
    )
    
    # Create replies
    replies = []
    for i in range(2):
        reply = message_service.create_message(
            channel_id=channel.id,
            user_id=user.id,
            content=f"Reply {i}",
            thread_id=parent.id
        )
        replies.append(reply)
    
    # Get thread messages
    thread_messages = message_service.get_thread_messages(parent.id)
    assert len(thread_messages) == 2
    assert all(m.thread_id == parent.id for m in thread_messages)

def test_update_message(message_service, user_service, channel_service):
    """Test updating a message's content"""
    user = create_test_user(user_service)
    channel = create_test_channel(channel_service)
    
    # Create message
    message = message_service.create_message(
        channel_id=channel.id,
        user_id=user.id,
        content="Original content"
    )
    
    # Update message
    updated = message_service.update_message(
        message_id=message.id,
        content="Updated content"
    )
    
    assert updated.content == "Updated content"
    assert updated.is_edited is True
    assert hasattr(updated, 'edited_at') 