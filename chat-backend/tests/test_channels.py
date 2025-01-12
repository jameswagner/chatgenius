import pytest
import boto3
from moto import mock_aws
from datetime import datetime, timezone
from app.services.channel_service import ChannelService
from app.services.user_service import UserService
from scripts.create_table import create_chat_table
from app.services.message_service import MessageService

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
def ddb(ddb_table):
    """ChannelService instance with mocked table."""
    return ChannelService(table_name='test_table')

@pytest.fixture
def user_service(ddb_table):
    """UserService instance with mocked table."""
    return UserService(table_name='test_table')

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

def test_create_public_channel(ddb, user_service):
    """Test creating a public channel."""
    # Create test user first
    create_test_user(user_service, "user123", "Test User")
    
    channel = ddb.create_channel(
        name="general-chat",
        type="public",
        created_by="user123"
    )
    
    assert channel.id is not None
    assert channel.name == "general-chat"
    assert channel.type == "public"
    assert channel.created_by == "user123"
    assert len(channel.members) == 1
    assert channel.members[0]['name'] == "Test User"

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
    
    assert channel.id is not None
    assert channel.type == "dm"
    member_names = {m['name'] for m in channel.members}
    assert member_names == {"User One", "User Two"}

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
    channel_names = {c.name for c in user_channels}
    assert channel_names == {"channel0", "channel1", "channel2"}

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
    channel_names = {c.name for c in available}
    assert channel_names == {"other-channel0", "other-channel1", "other-channel2"}

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
    assert channel.id == created.id
    assert channel.type == "dm"
    member_names = {m['name'] for m in channel.members}
    assert member_names == {"User One", "User Two"}

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
    ddb.add_channel_member(channel.id, new_member_id)
    
    # Get updated members
    members = ddb.get_channel_members(channel.id)
    assert len(members) == 2
    member_names = {m['name'] for m in members}
    assert member_names == {"Creator", "New User"}

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
        ddb.add_channel_member(channel.id, "user1")

def test_get_channel_members_empty(ddb, user_service):
    """Test getting members of an empty channel."""
    # Create test user
    create_test_user(user_service, "creator", "Creator")
    
    channel = ddb.create_channel(
        name="empty-channel",
        type="public",
        created_by="creator"
    )
    
    members = ddb.get_channel_members(channel.id)
    assert len(members) == 1
    assert members[0]['name'] == "Creator"

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

    # Add some messages using the new format
    timestamp = datetime.now(timezone.utc).isoformat()
    for i in range(5):
        message_id = f"msg{i}"
        ddb.table.put_item(Item={
            'PK': f'MSG#{message_id}',
            'SK': f'MSG#{message_id}',
            'GSI1PK': f'CHANNEL#{channel.id}',
            'GSI1SK': f'TS#{timestamp}',
            'content': f'Message {i}',
            'user_id': 'user1',
            'channel_id': channel.id,
            'created_at': timestamp,
            'id': message_id
        })

    count = ddb.get_channel_message_count(channel.id)
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
    other_user = ddb.get_other_dm_user(channel.id, user1_id)
    assert other_user == user2_id
    
    # Get other user from user2's perspective
    other_user = ddb.get_other_dm_user(channel.id, user2_id)
    assert other_user == user1_id

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
        ddb.get_other_dm_user(channel.id, "user1")

def test_mark_channel_read(ddb, user_service):
    """Test marking a channel as read"""
    # Create a test user
    user = ddb.create_user("test@example.com", "Test User", "password")
    
    # Add user to channel
    ddb.add_channel_member(channel.id, user.id)
    
    # Create some test messages
    message1 = ddb.create_message(channel.id, user.id, "Message 1")
    message2 = ddb.create_message(channel.id, user.id, "Message 2")
    message3 = ddb.create_message(channel.id, user.id, "Message 3")
    
    # Get channels for user - should show unread messages
    channels = ddb.get_channels_for_user(user.id)
    assert len(channels) == 1
    assert channels[0].unread_count == 3
    
    # Mark channel as read
    ddb.mark_channel_read(channel.id, user.id)
    
    # Check unread count is now 0
    channels = ddb.get_channels_for_user(user.id)
    assert len(channels) == 1
    assert channels[0].unread_count == 0
    
    # Add new message
    message4 = ddb.create_message(channel.id, user.id, "Message 4")
    
    # Check unread count is now 1
    channels = ddb.get_channels_for_user(user.id)
    assert len(channels) == 1
    assert channels[0].unread_count == 1

def test_unread_counts_multiple_channels(ddb):
    """Test unread counts across multiple channels"""
    # Create test users
    user1 = ddb.create_user("user1@example.com", "User 1", "password")
    user2 = ddb.create_user("user2@example.com", "User 2", "password")
    
    # Create two channels
    channel1 = ddb.create_channel("Channel 1", created_by=user1.id)
    channel2 = ddb.create_channel("Channel 2", created_by=user1.id)
    
    # Add user2 to both channels
    ddb.add_channel_member(channel1.id, user2.id)
    ddb.add_channel_member(channel2.id, user2.id)
    
    # Create messages in both channels
    ddb.create_message(channel1.id, user1.id, "Channel 1 Message 1")
    ddb.create_message(channel1.id, user1.id, "Channel 1 Message 2")
    ddb.create_message(channel2.id, user1.id, "Channel 2 Message 1")
    
    # Check initial unread counts for user2
    channels = ddb.get_channels_for_user(user2.id)
    channel1_data = next(c for c in channels if c.id == channel1.id)
    channel2_data = next(c for c in channels if c.id == channel2.id)
    assert channel1_data.unread_count == 2
    assert channel2_data.unread_count == 1
    
    # Mark channel1 as read
    ddb.mark_channel_read(channel1.id, user2.id)
    
    # Verify counts after marking channel1 as read
    channels = ddb.get_channels_for_user(user2.id)
    channel1_data = next(c for c in channels if c.id == channel1.id)
    channel2_data = next(c for c in channels if c.id == channel2.id)
    assert channel1_data.unread_count == 0
    assert channel2_data.unread_count == 1
    
    # Add new message to channel1
    ddb.create_message(channel1.id, user1.id, "Channel 1 Message 3")
    
    # Verify counts after new message
    channels = ddb.get_channels_for_user(user2.id)
    channel1_data = next(c for c in channels if c.id == channel1.id)
    channel2_data = next(c for c in channels if c.id == channel2.id)
    assert channel1_data.unread_count == 1
    assert channel2_data.unread_count == 1

def test_mark_channel_read_permissions(ddb, channel):
    """Test permissions for marking channel as read"""
    # Create test users
    user1 = ddb.create_user("user1@example.com", "User 1", "password")
    user2 = ddb.create_user("user2@example.com", "User 2", "password")
    
    # Add only user1 to channel
    ddb.add_channel_member(channel.id, user1.id)
    
    # Create a test message
    ddb.create_message(channel.id, user1.id, "Test Message")
    
    # User1 should be able to mark as read
    ddb.mark_channel_read(channel.id, user1.id)
    
    # User2 should not be able to mark as read
    try:
        ddb.mark_channel_read(channel.id, user2.id)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert str(e) == "User is not a member" 