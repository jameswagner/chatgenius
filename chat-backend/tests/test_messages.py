import pytest
import boto3
from moto import mock_aws
from app.db.ddb import DynamoDB
from app.models.message import Message

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
    table = dynamodb.create_table(
        TableName='test_table',
        KeySchema=[
            {'AttributeName': 'PK', 'KeyType': 'HASH'},
            {'AttributeName': 'SK', 'KeyType': 'RANGE'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'PK', 'AttributeType': 'S'},
            {'AttributeName': 'SK', 'AttributeType': 'S'}
        ],
        BillingMode='PAY_PER_REQUEST'
    )
    return table

@pytest.fixture
def ddb(ddb_table):
    """DynamoDB instance with mocked table."""
    return DynamoDB(table_name='test_table')

def test_create_message(ddb):
    """Test creating a basic message."""
    message = ddb.create_message(
        channel_id="test_channel",
        user_id="test_user",
        content="Hello, world!"
    )
    
    assert message.id is not None
    assert message.channel_id == "test_channel"
    assert message.user_id == "test_user"
    assert message.content == "Hello, world!" 