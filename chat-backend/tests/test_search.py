import pytest
import boto3
from moto import mock_aws
from datetime import datetime, timezone
from app.services.search_service import SearchService
from app.services.user_service import UserService
from app.services.channel_service import ChannelService
from scripts.create_table import create_chat_table

@pytest.fixture
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    import os
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'

@pytest.fixture
def dynamodb(aws_credentials):
    """Create mock DynamoDB."""
    with mock_aws():
        yield boto3.resource('dynamodb')

@pytest.fixture
def ddb_table(dynamodb):
    """Create mock DynamoDB table with required schema."""
    return create_chat_table('test_table')

@pytest.fixture
def search_service(ddb_table):
    """SearchService instance with mocked table."""
    return SearchService(table_name='test_table')

@pytest.fixture
def user_service(ddb_table):
    """UserService instance with mocked table."""
    return UserService(table_name='test_table')

@pytest.fixture
def channel_service(ddb_table):
    """ChannelService instance with mocked table."""
    return ChannelService(table_name='test_table')

def create_test_user(user_service, user_id: str, name: str) -> dict:
    """Create a test user."""
    print(f"\n=== Creating user: email={user_id}@test.com, name={name}, type=user ===")
    return user_service.create_user(
        email=f"{user_id}@test.com",
        name=name,
        password="password123",
        type="user",
        id=user_id
    )

def create_test_message(search_service, channel_id: str, user_id: str, content: str) -> None:
    """Create a test message directly in DynamoDB."""
    timestamp = datetime.now(timezone.utc).isoformat()
    message_id = search_service._generate_id()
    
    # Create message item
    message_item = {
        'PK': f'CHANNEL#{channel_id}',
        'SK': f'MSG#{timestamp}#{message_id}',
        'GSI1PK': f'USER#{user_id}',
        'GSI1SK': f'TS#{timestamp}',
        'id': message_id,
        'channel_id': channel_id,
        'user_id': user_id,
        'content': content,
        'created_at': timestamp,
        'version': 1
    }
    search_service.table.put_item(Item=message_item)
    
    # Index only full words for search
    words = set(content.lower().split())
    for word in words:
        word_item = {
            'PK': f'WORD#{word}',
            'SK': f'MESSAGE#{message_id}',
            'GSI3PK': f'CONTENT#{word}',
            'GSI3SK': f'TS#{timestamp}',
            'message_id': message_id
        }
        search_service.table.put_item(Item=word_item)
    
    return message_id

def test_search_messages(search_service, user_service, channel_service):
    """Test searching messages across channels."""
    # Create test users
    create_test_user(user_service, "user1", "User One")
    create_test_user(user_service, "user2", "User Two")
    
    # Create channels
    channel1 = channel_service.create_channel(
        name="channel1",
        type="public",
        created_by="user1"
    )
    channel2 = channel_service.create_channel(
        name="channel2",
        type="public",
        created_by="user2"
    )
    
    # Add user1 to channel2
    channel_service.add_channel_member(channel2.id, "user1")
    
    # Create test messages
    create_test_message(search_service, channel1.id, "user1", "Hello world")
    create_test_message(search_service, channel1.id, "user1", "Testing search functionality")
    create_test_message(search_service, channel2.id, "user2", "Another hello message")
    create_test_message(search_service, channel2.id, "user2", "Message without match")
    
    # Search for "hello" - should find 2 messages
    results = search_service.search_messages("user1", "hello")
    assert len(results) == 2
    assert all("hello" in msg.content.lower() for msg in results)
    
    # Search for "testing" - should find 1 message
    results = search_service.search_messages("user1", "testing")
    assert len(results) == 1
    assert "testing" in results[0].content.lower()

def test_search_messages_channel_access(search_service, user_service, channel_service):
    """Test that users can only search messages in channels they have access to."""
    # Create test users
    create_test_user(user_service, "user1", "User One")
    create_test_user(user_service, "user2", "User Two")
    
    # Create channels
    channel1 = channel_service.create_channel(
        name="channel1",
        type="public",
        created_by="user1"
    )
    channel2 = channel_service.create_channel(
        name="channel2",
        type="public",
        created_by="user2"
    )
    
    # Create test messages
    create_test_message(search_service, channel1.id, "user1", "Hello world")
    create_test_message(search_service, channel2.id, "user2", "Hello everyone")
    
    # user2 should only see their message
    results = search_service.search_messages("user2", "hello")
    assert len(results) == 1
    assert results[0].channel_id == channel2.id

def test_search_messages_with_user_data(search_service, user_service, channel_service):
    """Test that search results include user data."""
    # Create test users
    user1 = create_test_user(user_service, "user1", "User One")
    create_test_user(user_service, "user2", "User Two")
    
    # Create channel
    channel = channel_service.create_channel(
        name="channel1",
        type="public",
        created_by="user1"
    )
    
    # Create test message
    create_test_message(search_service, channel.id, "user1", "Hello world")
    
    # Search and verify user data
    results = search_service.search_messages("user1", "hello")
    assert len(results) == 1
    assert results[0].user.id == user1.id
    assert results[0].user.name == user1.name

def test_search_messages_limit(search_service, user_service, channel_service):
    """Test that search results are limited to 50 messages."""
    # Create test users
    create_test_user(user_service, "user1", "User One")
    
    # Create channel
    channel = channel_service.create_channel(
        name="channel1",
        type="public",
        created_by="user1"
    )
    
    # Create 60 test messages
    for i in range(60):
        create_test_message(search_service, channel.id, "user1", f"Hello message {i}")
    
    # Search should return only 50 messages
    results = search_service.search_messages("user1", "hello")
    assert len(results) == 50 