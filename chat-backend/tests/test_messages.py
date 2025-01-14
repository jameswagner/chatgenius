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
                {'AttributeName': 'GSI3SK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI4PK', 'AttributeType': 'S'},
                {'AttributeName': 'GSI4SK', 'AttributeType': 'S'}
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'GSI1',
                    'KeySchema': [
                        {'AttributeName': 'GSI1PK', 'KeyType': 'HASH'},
                        {'AttributeName': 'GSI1SK', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                },
                {
                    'IndexName': 'GSI2',
                    'KeySchema': [
                        {'AttributeName': 'GSI2PK', 'KeyType': 'HASH'},
                        {'AttributeName': 'GSI2SK', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                },
                {
                    'IndexName': 'GSI3',
                    'KeySchema': [
                        {'AttributeName': 'GSI3PK', 'KeyType': 'HASH'},
                        {'AttributeName': 'GSI3SK', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                },
                {
                    'IndexName': 'GSI4',
                    'KeySchema': [
                        {'AttributeName': 'GSI4PK', 'KeyType': 'HASH'},
                        {'AttributeName': 'GSI4SK', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                }
            ],
            BillingMode='PAY_PER_REQUEST'
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
    
    # Verify reply
    assert reply.thread_id == parent.id
    
    # Verify both messages appear in channel messages
    channel_messages = message_service.get_messages(channel.id)
    assert len(channel_messages) == 2  # Parent message + reply
    
    # Verify reply appears in thread messages
    thread_messages = message_service.get_thread_messages(parent.id)
    assert len(thread_messages) == 1
    assert thread_messages[0].id == reply.id
    assert thread_messages[0].thread_id == parent.id

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
    for i in range(3):
        reply = message_service.create_message(
            channel_id=channel.id,
            user_id=user.id,
            content=f"Reply {i}",
            thread_id=parent.id
        )
        replies.append(reply)
    
    # Get thread messages
    thread_messages = message_service.get_thread_messages(parent.id)
    
    # Verify only replies are returned (not parent message)
    assert len(thread_messages) == 3
    assert all(msg.thread_id == parent.id for msg in thread_messages)
    
    # Verify chronological order
    assert all(thread_messages[i].created_at <= thread_messages[i+1].created_at 
              for i in range(len(thread_messages)-1))
    
    # Verify content matches
    for i, msg in enumerate(thread_messages):
        assert msg.content == f"Reply {i}"

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

def test_get_messages_with_threads(message_service, user_service, channel_service):
    """Test retrieving messages including thread replies"""
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
    for i in range(3):
        reply = message_service.create_message(
            channel_id=channel.id,
            user_id=user.id,
            content=f"Reply {i}",
            thread_id=parent.id
        )
        replies.append(reply)

    # Create another regular message
    regular = message_service.create_message(
        channel_id=channel.id,
        user_id=user.id,
        content="Regular message"
    )

    # Get channel messages - should include all messages in chronological order
    channel_messages = message_service.get_messages(channel.id)
    assert len(channel_messages) == 5  # Parent + 3 replies + regular message
    
    # Verify thread messages
    thread_messages = message_service.get_thread_messages(parent.id)
    assert len(thread_messages) == 3  # Just the replies
    for i, msg in enumerate(thread_messages):
        assert msg.content == f"Reply {i}"
        assert msg.thread_id == parent.id

def test_get_message_with_thread_id(message_service, user_service, channel_service):
    """Test retrieving a message using thread_id parameter"""
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
    
    # Get reply using thread_id
    retrieved = message_service.get_message(reply.id, thread_id=parent.id)
    assert retrieved is not None
    assert retrieved.id == reply.id
    assert retrieved.content == reply.content
    assert retrieved.thread_id == parent.id
    
    # Verify user data is attached
    assert retrieved.user is not None
    assert retrieved.user.id == user.id
    assert retrieved.user.name == user.name 

def test_get_user_messages(message_service, user_service, channel_service):
    """Test retrieving all messages created by a user"""
    # Create two users
    user1 = create_test_user(user_service, "user1", "User One")
    user2 = create_test_user(user_service, "user2", "User Two")
    channel = create_test_channel(channel_service)
    
    # Create messages from both users
    user1_messages = []
    for i in range(3):
        msg = message_service.create_message(
            channel_id=channel.id,
            user_id=user1.id,
            content=f"User1 Message {i}"
        )
        user1_messages.append(msg)
    
    # Create messages from user2
    for i in range(2):
        message_service.create_message(
            channel_id=channel.id,
            user_id=user2.id,
            content=f"User2 Message {i}"
        )
    
    # Get user1's messages
    messages = message_service.get_user_messages(user1.id)
    
    # Verify only user1's messages are returned
    assert len(messages) == 3
    assert all(msg.user_id == user1.id for msg in messages)
    assert all(msg.user.id == user1.id for msg in messages)
    
    # Verify messages are in reverse chronological order
    assert all(messages[i].created_at >= messages[i+1].created_at 
              for i in range(len(messages)-1))

def test_get_user_messages_with_pagination(message_service, user_service, channel_service):
    """Test pagination of user messages"""
    user = create_test_user(user_service)
    channel = create_test_channel(channel_service)
    
    # Create 5 messages
    messages = []
    for i in range(5):
        msg = message_service.create_message(
            channel_id=channel.id,
            user_id=user.id,
            content=f"Message {i}"
        )
        messages.append(msg)
    
    # Get first 2 messages
    first_page = message_service.get_user_messages(user.id, limit=2)
    assert len(first_page) == 2
    
    # Get next page using the last message's timestamp
    second_page = message_service.get_user_messages(
        user_id=user.id,
        before=first_page[-1].created_at,
        limit=2
    )
    assert len(second_page) == 2
    
    # Verify no duplicate messages between pages
    first_ids = {msg.id for msg in first_page}
    second_ids = {msg.id for msg in second_page}
    assert not (first_ids & second_ids)  # No intersection
    
    # Verify chronological order across pages
    assert all(first_page[i].created_at >= first_page[i+1].created_at 
              for i in range(len(first_page)-1))
    assert all(second_page[i].created_at >= second_page[i+1].created_at 
              for i in range(len(second_page)-1))
    assert first_page[-1].created_at >= second_page[0].created_at

def test_get_user_messages_includes_thread_replies(message_service, user_service, channel_service):
    """Test that get_user_messages includes thread replies"""
    user = create_test_user(user_service)
    channel = create_test_channel(channel_service)
    
    # Create a parent message
    parent = message_service.create_message(
        channel_id=channel.id,
        user_id=user.id,
        content="Parent message"
    )
    
    # Create some replies in the thread
    replies = []
    for i in range(2):
        reply = message_service.create_message(
            channel_id=channel.id,
            user_id=user.id,
            content=f"Reply {i}",
            thread_id=parent.id
        )
        replies.append(reply)
    
    # Get user's messages
    messages = message_service.get_user_messages(user.id)
    
    # Should include both parent and replies
    assert len(messages) == 3
    
    # Verify we have both types of messages
    parent_messages = [m for m in messages if not m.thread_id]
    reply_messages = [m for m in messages if m.thread_id]
    
    assert len(parent_messages) == 1
    assert len(reply_messages) == 2
    
    # Verify thread relationships
    for reply in reply_messages:
        assert reply.thread_id == parent.id

def test_get_user_messages_invalid_user(message_service):
    """Test getting messages for non-existent user"""
    with pytest.raises(ValueError, match="User not found"):
        message_service.get_user_messages("nonexistent_user") 