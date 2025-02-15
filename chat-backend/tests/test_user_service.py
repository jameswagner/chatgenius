import pytest
import boto3
from moto import mock_aws
from app.services.user_service import UserService
from app.models.user import User
from tests.utils import create_chat_table

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
    """UserService instance with mocked table."""
    return UserService(table_name='test_table')

def test_create_user(ddb):
    """Test creating a user."""
    user = ddb.create_user(
        email="test@example.com",
        name="Test User",
        password="password123",
        type="user"
    )
    
    assert user.id is not None
    assert user.email == "test@example.com"
    assert user.name == "Test User"
    assert user.type == "user"
    assert user.status == "online"
    assert user.created_at is not None

def test_get_user_by_email(ddb):
    """Test retrieving a user by email."""
    # Create a user first
    created_user = ddb.create_user(
        email="find@example.com",
        name="Find Me",
        password="password123"
    )
    
    # Try to find the user
    found_user = ddb.get_user_by_email("find@example.com")
    
    assert found_user is not None
    assert found_user.id == created_user.id
    assert found_user.email == "find@example.com"
    assert found_user.status == "online"
    
    # Test non-existent user
    not_found = ddb.get_user_by_email("nonexistent@example.com")
    assert not_found is None

def test_get_user_by_id(ddb):
    """Test retrieving a user by ID."""
    # Create a user first
    created_user = ddb.create_user(
        email="findbyid@example.com",
        name="Find By ID",
        password="password123"
    )
    
    # Try to find the user
    found_user = ddb.get_user_by_id(created_user.id)
    
    assert found_user is not None
    assert found_user.id == created_user.id
    assert found_user.email == "findbyid@example.com"
    assert found_user.status == "online"
    
    # Test non-existent user
    not_found = ddb.get_user_by_id("nonexistent-id")
    assert not_found is None

def test_update_user_status(ddb):
    """Test updating a user's status."""
    # Create a user first
    user = ddb.create_user(
        email="status@example.com",
        name="Status User",
        password="password123"
    )
    
    # Update status to offline
    updated_user = ddb.update_user_status(user.id, "offline")
    
    assert updated_user is not None
    assert updated_user.id == user.id
    assert updated_user.status == "offline"
    
    # Verify status is persisted
    found_user = ddb.get_user_by_id(user.id)
    assert found_user.status == "offline"
    assert found_user.last_active is not None

def test_get_all_users(ddb):
    """Test retrieving all users."""
    # Create multiple users
    users = [
        ddb.create_user(f"user{i}@example.com", f"User {i}", "password123")
        for i in range(3)
    ]
    
    # Get all users
    all_users = ddb.get_all_users()
    
    assert len(all_users) >= 3  # Could be more if other tests created users
    created_ids = {user.id for user in users}
    found_ids = {user['id'] for user in all_users}
    assert created_ids.issubset(found_ids)
    
    # Verify only essential fields are returned
    for user in all_users:
        assert set(user.keys()) == {'id', 'name', 'email'}

def test_get_persona_users(ddb):
    """Test retrieving persona users."""
    # Create regular and persona users
    regular_user = ddb.create_user(
        "regular@example.com", "Regular", "password123", type="user"
    )
    persona = ddb.create_user(
        "persona@example.com", "Persona", "password123", type="persona",
        role="Assistant", bio="I help with testing"
    )
    
    # Get persona users
    personas = ddb.get_persona_users()
    
    # Should only return persona users
    assert len(personas) == 1
    assert personas[0].id == persona.id
    assert personas[0].type == "persona"
    assert personas[0].role == "Assistant"
    assert personas[0].bio == "I help with testing"

def test_batch_get_users(ddb):
    """Test batch getting multiple users."""
    # Create multiple users
    users = [
        ddb.create_user(f"batch{i}@example.com", f"Batch User {i}", "password123")
        for i in range(5)
    ]
    user_ids = {user.id for user in users}
    
    # Batch get users
    found_users = ddb._batch_get_users(user_ids)
    
    assert len(found_users) == 5
    found_ids = {user.id for user in found_users}
    assert found_ids == user_ids
    
    # Test with empty set
    empty_result = ddb._batch_get_users(set())
    assert empty_result == [] 

def test_get_user_by_name(ddb):
    """Test retrieving a user by username."""
    # Create a user first
    created_user = ddb.create_user(
        email="findbyname@example.com",
        name="FindByName",
        password="password123"
    )
    
    # Try to find the user
    found_user = ddb.get_user_by_name("FindByName")
    
    assert found_user is not None
    assert found_user.id == created_user.id
    assert found_user.name == "FindByName"
    assert found_user.status == "online"
    
    # Test non-existent user
    not_found = ddb.get_user_by_name("NonexistentUser")
    assert not_found is None

def test_username_uniqueness(ddb):
    """Test that usernames must be unique."""
    # Create first user
    ddb.create_user(
        email="user1@example.com",
        name="SameUsername",
        password="password123"
    )
    
    # Try to create second user with same username
    with pytest.raises(ValueError) as exc_info:
        ddb.create_user(
            email="user2@example.com",
            name="SameUsername",
            password="password123"
        )
    assert "Username is already taken" in str(exc_info.value)
    
    # Verify different username works
    user2 = ddb.create_user(
        email="user2@example.com",
        name="DifferentUsername",
        password="password123"
    )
    assert user2 is not None
    assert user2.name == "DifferentUsername" 