from flask import Blueprint, request, jsonify
from app.auth.auth_service import auth_required
from app.db.ddb import DynamoDB
import os
from app.services.workspace_service import WorkspaceService

bp = Blueprint('workspaces', __name__, url_prefix='/workspaces')
db = DynamoDB(table_name=os.environ.get('DYNAMODB_TABLE', 'chat_app_jrw'))

@bp.route('', methods=['POST'])
@auth_required
def create_workspace():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({'error': 'Workspace name is required'}), 400
    workspace = db.create_workspace(data['name'])
    return jsonify(workspace.to_dict()), 201

@bp.route('/<workspace_id>', methods=['GET', 'OPTIONS'])
@auth_required
def get_workspace(workspace_id):
    workspace = db.get_workspace_by_id(workspace_id)
    if not workspace:
        return jsonify({'error': 'Workspace not found'}), 404
    return jsonify(workspace.to_dict())

@bp.route('', methods=['GET'])
@auth_required
def get_all_workspaces():
    #look up user from request user_id
    user = db.get_user_by_id(request.user_id)
    if user.type == 'persona':
        #get all workspaces that the persona is a member of
        print(f"Getting all workspaces for persona {user.id}")
        workspaces = WorkspaceService().get_all_workspaces(user.id)
    else:
        workspaces = WorkspaceService().get_all_workspaces()
    return jsonify([workspace.to_dict() for workspace in workspaces])

@bp.route('/<workspace_id>/members', methods=['GET'])
@auth_required
def get_users_in_workspace(workspace_id):
    """Retrieve users who are members of at least one channel in the specified workspace."""
    users = db.get_users_by_workspace(workspace_id)
    return jsonify([user.to_dict() for user in users])

@bp.route('/<workspace_id>/members', methods=['POST'])
def add_user_to_workspace(workspace_id):
    user_id = request.json.get('user_id')
    db.add_user_to_workspace(workspace_id, user_id)
    return jsonify({'message': 'User added to workspace successfully'}), 201

@bp.route('/users/<user_id>/workspaces', methods=['GET'])
def get_workspaces_by_user(user_id):
    workspaces = db.get_workspaces_by_user(user_id)
    return jsonify(workspaces), 200 