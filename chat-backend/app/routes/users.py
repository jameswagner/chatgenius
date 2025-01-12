from flask import Blueprint, request, jsonify
from app.auth.auth_service import auth_required
from app.db.ddb import DynamoDB
from app import get_socketio
import os
from datetime import datetime, timezone

bp = Blueprint('users', __name__)
db = DynamoDB(table_name=os.environ.get('DYNAMODB_TABLE', 'chat_app_jrw'))
socketio = get_socketio()

@bp.route('/', strict_slashes=False)
@auth_required
def get_users():
    users = db.user_service.get_all_users()
    return jsonify(users)

@bp.route('/status', methods=['PUT'], strict_slashes=False)
@auth_required
def update_status():
    """Update the current user's status"""
    data = request.get_json()
    print(f"[STATUS] 1. Request received with data: {data}")
    
    if 'status' not in data:
        return jsonify({'error': 'Status is required'}), 400
        
    valid_statuses = ['online', 'away', 'busy', 'offline']
    if data['status'] not in valid_statuses:
        return jsonify({'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}), 400
    
    try:
        print(f"[STATUS] 2. Updating user {request.user_id} to status: {data['status']}")
        user = db.update_user_status(request.user_id, data['status'])
        if not user:
            return jsonify({'error': 'User not found'}), 404

        print(f"[STATUS] 3. User object after update: {user.to_dict()}")
        user_dict = user.to_dict()
        
        # Use the requested status directly, not the one from the user object
        status_update = {
            'userId': user.id,
            'status': data['status'],
            'lastActive': user_dict['lastActive']
        }
        
        print(f"[STATUS] 4. Emitting status update: {status_update}")
        socketio.emit('user.status', status_update)
        
        return jsonify(user_dict)
    except Exception as e:
        print(f"[STATUS] ERROR: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/me', strict_slashes=False)
@auth_required
def get_current_user():
    """Get current user's data"""
    user = db.get_user_by_id(request.user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(user.to_dict())

@bp.route('/personas', methods=['GET'], strict_slashes=False)
def get_personas():
    personas = [
        {'id': '1', 'name': 'Alice', 'email': 'alice@example.com'},
        {'id': '2', 'name': 'Bob', 'email': 'bob@example.com'},
        {'id': '3', 'name': 'Charlie', 'email': 'charlie@example.com'}
    ]
    return jsonify(personas) 