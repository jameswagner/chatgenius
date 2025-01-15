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
    workspaces = WorkspaceService().get_all_workspaces()
    return jsonify([workspace.to_dict() for workspace in workspaces]) 