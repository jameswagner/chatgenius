import pytest
from moto import mock_dynamodb
import boto3
from datetime import datetime, timezone
from app.services.channel_service import ChannelService
from app.services.user_service import UserService

@pytest.fixture
def ddb():
    """Create a mock DynamoDB table."""
    with mock_dynamodb():
        # Create mock credentials
        boto3.setup_default_session(
            aws_access_key_id="testing",
            aws_secret_access_key="testing",
            aws_session_token="testing",
        )
        
        # Create DynamoDB resource and table
        dynamodb = boto3.resource("dynamodb", region_name="us-west-2")
        
        # Create table with GSI
        table = dynamodb.create_table(
            TableName="test-table",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"}
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
                {"AttributeName": "GSI1PK", "AttributeType": "S"},
                {"AttributeName": "GSI1SK", "AttributeType": "S"},
                {"AttributeName": "GSI2PK", "AttributeType": "S"},
                {"AttributeName": "GSI2SK", "AttributeType": "S"}
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "GSI1",
                    "KeySchema": [
                        {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI1SK", "KeyType": "RANGE"}
                    ],
                    "Projection": {"ProjectionType": "ALL"}
                },
                {
                    "IndexName": "GSI2",
                    "KeySchema": [
                        {"AttributeName": "GSI2PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI2SK", "KeyType": "RANGE"}
                    ],
                    "Projection": {"ProjectionType": "ALL"}
                }
            ],
            BillingMode="PAY_PER_REQUEST"
        )
        
        yield ChannelService("test-table")

@pytest.fixture
def user_service():
    """Create a UserService instance with mock DynamoDB."""
    with mock_dynamodb():
        # Create mock credentials
        boto3.setup_default_session(
            aws_access_key_id="testing",
            aws_secret_access_key="testing",
            aws_session_token="testing",
        )
        
        # Create DynamoDB resource and table
        dynamodb = boto3.resource("dynamodb", region_name="us-west-2")
        
        # Create table with GSI
        table = dynamodb.create_table(
            TableName="test-table",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"}
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
                {"AttributeName": "GSI1PK", "AttributeType": "S"},
                {"AttributeName": "GSI1SK", "AttributeType": "S"},
                {"AttributeName": "GSI2PK", "AttributeType": "S"},
                {"AttributeName": "GSI2SK", "AttributeType": "S"}
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "GSI1",
                    "KeySchema": [
                        {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI1SK", "KeyType": "RANGE"}
                    ],
                    "Projection": {"ProjectionType": "ALL"}
                },
                {
                    "IndexName": "GSI2",
                    "KeySchema": [
                        {"AttributeName": "GSI2PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI2SK", "KeyType": "RANGE"}
                    ],
                    "Projection": {"ProjectionType": "ALL"}
                }
            ],
            BillingMode="PAY_PER_REQUEST"
        )
        
        yield UserService("test-table")

def create_test_user(user_service: UserService, user_id: str, name: str):
    """Helper function to create a test user."""
    print(f"\n=== Creating user: email={user_id}@test.com, name={name}, type=user ===")
    user = {
        'id': user_id,
        'email': f"{user_id}@test.com",
        'name': name,
        'password': 'password123',
        'type': 'user'
    }
    return user_service.create_user(**user)

def test_create_public_channel(ddb, user_service):
    """Test creating a public channel."""
    # Create test user first
    create_test_user(user_service, "user123", "Test User")
    
    channel = ddb.create_channel(
        name="general-chat",
        type="public",
        created_by="user123"
    )
    
    assert channel.get('id') is not None
    assert channel.get('name') == "general-chat"
    assert channel.get('type') == "public"
    assert channel.get('created_by') == "user123"
    assert channel.get('created_at') is not None
    assert isinstance(channel.get('members'), list)
    assert len(channel.get('members')) == 1  # Creator should be added as member
    assert channel.get('members')[0].get('name') == "Test User"

def test_create_dm_channel(ddb, user_service):
    """Test creating a DM channel between two users."""
    # Create test users first
    create_test_user(user_service, "user1", "User One")
    create_test_user(user_service, "user2", "User Two")
    
    user1_id = "user1"
    user2_id = "user2"
    
    channel = ddb.create_channel(
        name="dm",
        type="dm",
        created_by=user1_id,
        other_user_id=user2_id
    )
    
    assert channel.get('id') is not None
    assert channel.get('type') == "dm"
    assert channel.get('created_by') == user1_id
    assert isinstance(channel.get('members'), list)
    assert len(channel.get('members')) == 2
    member_names = {m.get('name') for m in channel.get('members')}
    assert "User One" in member_names
    assert "User Two" in member_names

def test_get_channel_by_id_nonexistent(ddb, user_service):
    """Test getting a non-existent channel."""
    channel = ddb.get_channel_by_id("nonexistent")
    assert channel is None

def test_get_channels_for_user(ddb, user_service):
    """Test getting all channels for a user."""
    # Create test users
    create_test_user(user_service, "test_user", "Test User")
    create_test_user(user_service, "other_user", "Other User")
    
    user_id = "test_user"
    
    # Create multiple channels
    channels = [
        ddb.create_channel(f"channel{i}", "public", created_by=user_id)
        for i in range(3)
    ]
    
    # Get channels for user
    user_channels = ddb.get_channels_for_user(user_id)
    
    assert len(user_channels) == 3
    channel_names = {c.get('name') for c in user_channels}
    assert all(f"channel{i}" in channel_names for i in range(3))

def test_get_available_channels(ddb, user_service):
    """Test getting available public channels for a user."""
    # Create test users
    create_test_user(user_service, "test_user", "Test User")
    create_test_user(user_service, "other_user", "Other User")
    
    user_id = "test_user"
    
    # Create channels user is part of
    member_channels = [
        ddb.create_channel(f"member-channel{i}", "public", created_by=user_id)
        for i in range(2)
    ]
    
    # Create channels user is not part of
    other_channels = [
        ddb.create_channel(f"other-channel{i}", "public", created_by="other_user")
        for i in range(3)
    ]
    
    # Get available channels
    available = ddb.get_available_channels(user_id)
    
    # Should only see channels they're not a member of
    assert len(available) == 3
    channel_names = {c.get('name') for c in available}
    assert all(f"other-channel{i}" in channel_names for i in range(3))

def test_get_dm_channel(ddb, user_service):
    """Test getting a DM channel between users."""
    # Create test users
    create_test_user(user_service, "user1", "User One")
    create_test_user(user_service, "user2", "User Two")
    
    user1_id = "user1"
    user2_id = "user2"
    
    # Create DM channel
    created = ddb.create_channel(
        name="dm",
        type="dm",
        created_by=user1_id,
        other_user_id=user2_id
    )
    
    # Get DM channel
    channel = ddb.get_dm_channel(user1_id, user2_id)
    
    assert channel is not None
    assert channel.get('id') == created.get('id')
    assert channel.get('type') == "dm"
    assert len(channel.get('members')) == 2

def test_channel_name_uniqueness(ddb, user_service):
    """Test that public channels with the same name are not allowed."""
    # Create test users
    create_test_user(user_service, "user1", "User One")
    create_test_user(user_service, "user2", "User Two")
    
    name = "unique-channel"
    
    # Create first channel
    first = ddb.create_channel(name, "public", created_by="user1")
    
    # Try to create another channel with same name
    with pytest.raises(ValueError, match="Channel name already exists"):
        ddb.create_channel(name, "public", created_by="user2")

def test_dm_channel_uniqueness(ddb, user_service):
    """Test that only one DM channel can exist between two users."""
    # Create test users
    create_test_user(user_service, "user1", "User One")
    create_test_user(user_service, "user2", "User Two")
    
    user1_id = "user1"
    user2_id = "user2"
    
    # Create first DM channel
    first = ddb.create_channel(
        name="dm",
        type="dm",
        created_by=user1_id,
        other_user_id=user2_id
    )
    
    # Try to create another DM channel between same users
    with pytest.raises(ValueError, match="DM channel already exists"):
        ddb.create_channel(
            name="dm",
            type="dm",
            created_by=user2_id,
            other_user_id=user1_id
        )

def test_add_channel_member(ddb, user_service):
    """Test adding a member to a channel."""
    # Create test users
    create_test_user(user_service, "creator", "Creator")
    create_test_user(user_service, "new_user", "New User")
    
    # Create a channel
    channel = ddb.create_channel(
        name="test-channel",
        type="public",
        created_by="creator"
    )
    
    # Add a new member
    new_member_id = "new_user"
    ddb.add_channel_member(channel.get('id'), new_member_id)
    
    # Verify member was added
    members = ddb.get_channel_members(channel.get('id'))
    member_ids = {m.get('id') for m in members}
    assert new_member_id in member_ids
    
    # Verify member details
    new_member = next(m for m in members if m.get('id') == new_member_id)
    assert new_member.get('name') == "New User"
    assert new_member.get('joined_at') is not None
    assert new_member.get('last_read') is not None

def test_add_duplicate_channel_member(ddb, user_service):
    """Test adding a member who is already in the channel."""
    # Create test user
    create_test_user(user_service, "user1", "User One")
    
    channel = ddb.create_channel(
        name="test-channel",
        type="public",
        created_by="user1"
    )
    
    # Try to add the creator again
    with pytest.raises(ValueError, match="User is already a member"):
        ddb.add_channel_member(channel.get('id'), "user1")

def test_get_channel_members_empty(ddb, user_service):
    """Test getting members of an empty channel."""
    # Create test user
    create_test_user(user_service, "creator", "Creator")
    
    channel = ddb.create_channel(
        name="empty-channel",
        type="public",
        created_by="creator"
    )
    
    members = ddb.get_channel_members(channel.get('id'))
    assert len(members) == 1  # Just the creator
    assert members[0].get('name') == "Creator"

def test_get_channel_message_count(ddb, user_service):
    """Test getting message count for a channel."""
    # Create test user
    create_test_user(user_service, "user1", "User One")
    
    # Create a channel
    channel = ddb.create_channel(
        name="count-channel",
        type="public",
        created_by="user1"
    )
    
    # Add some messages directly to DynamoDB
    timestamp = datetime.now(timezone.utc).isoformat()
    for i in range(5):
        ddb.table.put_item(Item={
            'PK': f'CHANNEL#{channel.get("id")}',
            'SK': f'MSG#{timestamp}#{i}',
            'content': f'Message {i}',
            'sender': 'user1',
            'timestamp': timestamp
        })
    
    # Get message count
    count = ddb.get_channel_message_count(channel.get('id'))
    assert count == 5

def test_get_other_dm_user(ddb, user_service):
    """Test getting the other user in a DM channel."""
    # Create test users
    create_test_user(user_service, "user1", "User One")
    create_test_user(user_service, "user2", "User Two")
    
    user1_id = "user1"
    user2_id = "user2"
    
    # Create DM channel
    channel = ddb.create_channel(
        name="dm",
        type="dm",
        created_by=user1_id,
        other_user_id=user2_id
    )
    
    # Get other user from user1's perspective
    other_user = ddb.get_other_dm_user(channel.get('id'), user1_id)
    assert other_user.get('id') == user2_id
    assert other_user.get('name') == "User Two"
    
    # Get other user from user2's perspective
    other_user = ddb.get_other_dm_user(channel.get('id'), user2_id)
    assert other_user.get('id') == user1_id
    assert other_user.get('name') == "User One"

def test_get_other_dm_user_not_dm(ddb, user_service):
    """Test getting other DM user in a non-DM channel."""
    # Create test user
    create_test_user(user_service, "user1", "User One")
    
    channel = ddb.create_channel(
        name="public-channel",
        type="public",
        created_by="user1"
    )
    
    with pytest.raises(ValueError, match="Not a DM channel"):
        ddb.get_other_dm_user(channel.get('id'), "user1")

def test_mark_channel_read(ddb, user_service):
    """Test marking a channel as read."""
    # Create test users
    create_test_user(user_service, "user1", "User One")
    create_test_user(user_service, "user2", "User Two")
    
    # Create a channel with some messages
    channel = ddb.create_channel(
        name="read-channel",
        type="public",
        created_by="user1"
    )
    
    # Add another member
    ddb.add_channel_member(channel.get('id'), "user2")
    
    # Mark as read for user2
    ddb.mark_channel_read(channel.get('id'), "user2")
    
    # Verify last_read was updated
    members = ddb.get_channel_members(channel.get('id'))
    user2_member = next(m for m in members if m.get('id') == "user2")
    assert user2_member.get('last_read') is not None

def test_mark_channel_read_nonmember(ddb, user_service):
    """Test marking a channel as read for a non-member."""
    # Create test user
    create_test_user(user_service, "user1", "User One")
    
    channel = ddb.create_channel(
        name="test-channel",
        type="public",
        created_by="user1"
    )
    
    with pytest.raises(ValueError, match="User is not a member"):
        ddb.mark_channel_read(channel.get('id'), "nonmember") 