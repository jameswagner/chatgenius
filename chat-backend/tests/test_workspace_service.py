import pytest
import boto3
from moto import mock_aws
from app.services.workspace_service import WorkspaceService
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
def workspace_service(ddb_table):
    """WorkspaceService instance with mocked table."""
    return WorkspaceService(table_name='test_table')

# Ensure only workspace-related tests are included

def test_create_workspace(workspace_service):
    name = 'Test Workspace'
    workspace = workspace_service.create_workspace(name)
    assert workspace.name == name
    assert workspace.id is not None
    assert workspace.created_at is not None
    assert workspace.entity_type == 'WORKSPACE'

def test_get_workspace_by_id(workspace_service):
    name = 'Test Workspace'
    created_workspace = workspace_service.create_workspace(name)
    retrieved_workspace = workspace_service.get_workspace_by_id(created_workspace.id)
    assert retrieved_workspace is not None
    assert retrieved_workspace.id == created_workspace.id
    assert retrieved_workspace.name == created_workspace.name

def test_get_all_workspaces(workspace_service):
    name1 = 'Workspace One'
    name2 = 'Workspace Two'
    workspace_service.create_workspace(name1)
    workspace_service.create_workspace(name2)
    workspaces = workspace_service.get_all_workspaces()
    assert len(workspaces) == 2
    assert any(ws.name == name1 for ws in workspaces)
    assert any(ws.name == name2 for ws in workspaces)

def test_get_workspace_name_by_id(workspace_service):
    name = 'Test Workspace'
    created_workspace = workspace_service.create_workspace(name)
    workspace_name = workspace_service.get_workspace_name_by_id(created_workspace.id)
    assert workspace_name == name

def test_get_workspace_by_name(workspace_service):
    # Create a workspace
    workspace_name = "Test Workspace"
    workspace_service.create_workspace(name=workspace_name)

    # Retrieve the workspace by name
    workspace = workspace_service.get_workspace_by_name(name=workspace_name)
    print(f"Workspace: {workspace}")

    # Assertions
    assert workspace is not None
    assert workspace.name == workspace_name
    assert workspace.id is not None

# Add other workspace-related tests here

# Remove any channel-related tests

if __name__ == '__main__':
    pytest.main() 