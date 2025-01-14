import pytest
from unittest.mock import MagicMock, patch
from app.services.channel_service import ChannelService
from app.models.channel import Channel

@pytest.fixture
def channel_service():
    return ChannelService('test_table')

def test_create_channel_with_workspace(channel_service):
    # Mock DynamoDB table
    channel_service.table = MagicMock()
    channel_service.user_service = MagicMock()
    channel_service._generate_id = MagicMock(return_value='test_id')
    channel_service._now = MagicMock(return_value='2024-01-01T00:00:00Z')
    
    # Mock query for duplicate check to return no items
    channel_service.table.query.return_value = {'Items': []}
    
    # Mock get_channel_by_id for member addition
    channel_service.get_channel_by_id = MagicMock(return_value=Channel(
        id='test_id',
        name='test-channel',
        type='public',
        created_by='user1',
        created_at='2024-01-01T00:00:00Z',
        workspace_id='workspace1'
    ))
    
    # Create channel with workspace
    channel = channel_service.create_channel(
        name='test-channel',
        type='public',
        created_by='user1',
        workspace_id='workspace1'
    )
    
    # Verify channel was created with workspace
    assert channel.id == 'test_id'
    assert channel.name == 'test-channel'
    assert channel.workspace_id == 'workspace1'
    
    # Verify DynamoDB put_item was called for both channel and member
    assert channel_service.table.put_item.call_count == 2
    
    # Get the channel creation put_item call
    channel_put_args = None
    for call in channel_service.table.put_item.call_args_list:
        args = call[1]['Item']
        if args['SK'] == '#METADATA':
            channel_put_args = args
            break
    
    assert channel_put_args is not None
    assert channel_put_args['GSI4PK'] == 'WORKSPACE#workspace1'
    assert channel_put_args['GSI4SK'] == 'CHANNEL#test_id'

def test_create_channel_default_workspace(channel_service):
    # Mock DynamoDB table
    channel_service.table = MagicMock()
    channel_service.user_service = MagicMock()
    channel_service._generate_id = MagicMock(return_value='test_id')
    channel_service._now = MagicMock(return_value='2024-01-01T00:00:00Z')
    
    # Mock query for duplicate check to return no items
    channel_service.table.query.return_value = {'Items': []}
    
    # Mock get_channel_by_id for member addition
    channel_service.get_channel_by_id = MagicMock(return_value=Channel(
        id='test_id',
        name='test-channel',
        type='public',
        created_by='user1',
        created_at='2024-01-01T00:00:00Z'
    ))
    
    # Create channel without specifying workspace
    channel = channel_service.create_channel(
        name='test-channel',
        type='public',
        created_by='user1'
    )
    
    # Verify default workspace was used
    assert channel.workspace_id == 'NO_WORKSPACE'
    
    # Get the channel creation put_item call
    channel_put_args = None
    for call in channel_service.table.put_item.call_args_list:
        args = call[1]['Item']
        if args['SK'] == '#METADATA':
            channel_put_args = args
            break
    
    assert channel_put_args is not None
    assert channel_put_args['GSI4PK'] == 'WORKSPACE#NO_WORKSPACE'
    assert channel_put_args['GSI4SK'] == 'CHANNEL#test_id'

def test_find_channels_without_workspace(channel_service):
    # Mock DynamoDB table
    channel_service.table = MagicMock()
    timestamp = '2024-01-01T00:00:00Z'
    
    # Mock query responses for public and private channels
    channel_service.table.query.side_effect = [
        {   # Public channels
            'Items': [
                {   # Channel without workspace
                    'PK': 'CHANNEL#1',
                    'SK': '#METADATA',
                    'id': '1',
                    'name': 'channel1',
                    'type': 'public',
                    'created_by': 'user1',
                    'created_at': timestamp
                },
                {   # Channel with workspace (should be ignored)
                    'PK': 'CHANNEL#2',
                    'SK': '#METADATA',
                    'id': '2',
                    'name': 'channel2',
                    'type': 'public',
                    'created_by': 'user1',
                    'created_at': timestamp,
                    'workspace_id': 'workspace1'
                }
            ]
        },
        {   # Private channels
            'Items': [
                {   # Channel without workspace
                    'PK': 'CHANNEL#3',
                    'SK': '#METADATA',
                    'id': '3',
                    'name': 'channel3',
                    'type': 'private',
                    'created_by': 'user1',
                    'created_at': timestamp
                },
                {   # Channel with empty workspace (should be updated)
                    'PK': 'CHANNEL#4',
                    'SK': '#METADATA',
                    'id': '4',
                    'name': 'channel4',
                    'type': 'private',
                    'created_by': 'user1',
                    'created_at': timestamp,
                    'workspace_id': ''
                }
            ]
        }
    ]
    
    # Find and update channels without workspace
    channels = channel_service.find_channels_without_workspace()
    
    # Verify queries were called for both channel types
    assert channel_service.table.query.call_count == 2
    query_calls = channel_service.table.query.call_args_list
    
    # Verify first query was for public channels
    first_call = query_calls[0][1]
    assert first_call['IndexName'] == 'GSI1'
    assert first_call['KeyConditionExpression'].get_expression() == 'GSI1PK = :gsi1pk'
    assert first_call['KeyConditionExpression'].values[':gsi1pk'] == 'TYPE#public'
    
    # Verify second query was for private channels
    second_call = query_calls[1][1]
    assert second_call['IndexName'] == 'GSI1'
    assert second_call['KeyConditionExpression'].get_expression() == 'GSI1PK = :gsi1pk'
    assert second_call['KeyConditionExpression'].values[':gsi1pk'] == 'TYPE#private'
    
    # Verify update_item was called for channels without workspace
    assert channel_service.table.update_item.call_count == 3  # 2 without workspace + 1 with empty workspace
    
    # Verify returned channels
    assert len(channels) == 3
    channel_ids = [c.id for c in channels]
    assert '1' in channel_ids  # Public channel without workspace
    assert '3' in channel_ids  # Private channel without workspace
    assert '4' in channel_ids  # Private channel with empty workspace
    
    # Verify update_item calls had correct arguments
    for call in channel_service.table.update_item.call_args_list:
        args = call[1]
        assert args['UpdateExpression'] == 'SET workspace_id = :wid, GSI4PK = :wpk, GSI4SK = :csk'
        assert args['ExpressionAttributeValues'][':wid'] == 'NO_WORKSPACE'
        assert args['ExpressionAttributeValues'][':wpk'] == 'WORKSPACE#NO_WORKSPACE'

def test_assign_default_workspace_to_channels(channel_service):
    # Mock DynamoDB table
    channel_service.table = MagicMock()
    timestamp = '2024-01-01T00:00:00Z'
    
    # Mock find_channels_without_workspace to return test channels
    channel_service.find_channels_without_workspace = MagicMock(return_value=[
        Channel(
            id='1',
            name='channel1',
            type='public',
            created_by='user1',
            created_at=timestamp
        ),
        Channel(
            id='2',
            name='channel2',
            type='public',
            created_by='user1',
            created_at=timestamp
        )
    ])
    
    # Assign default workspace
    count = channel_service.assign_default_workspace_to_channels()
    
    # Verify count matches returned channels
    assert count == 2 