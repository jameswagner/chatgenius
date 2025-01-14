from flask import Blueprint, request, jsonify, send_from_directory
from app.auth.auth_service import auth_required
from app.db.ddb import DynamoDB
from app.storage.file_storage import FileStorage
from app import get_socketio
from flask_socketio import emit
import os
from datetime import datetime, timezone
import uuid
from werkzeug.utils import secure_filename
from flask_cors import cross_origin

bp = Blueprint('messages', __name__)
db = DynamoDB(table_name=os.environ.get('DYNAMODB_TABLE', 'chat_app_jrw'))
file_storage = FileStorage()
socketio = get_socketio()

@bp.route('/<message_id>/thread')
@cross_origin()
@auth_required
def get_thread_messages(message_id):
    messages = db.get_thread_messages(message_id)
    return jsonify([message.to_dict() for message in messages])

@bp.route('/<message_id>/thread', methods=['POST', 'OPTIONS'])
@cross_origin()
@auth_required
def create_thread_reply(message_id):
    if request.method == 'OPTIONS':
        return '', 200
        
    user_id = request.user_id
    data = request.get_json()
    
    # Get parent message to get channel_id
    parent_message = db.get_message(message_id)
    if not parent_message:
        return jsonify({'error': 'Parent message not found'}), 404
    
    message = db.create_message(
        channel_id=parent_message.channel_id,
        user_id=user_id,
        content=data['content'],
        thread_id=message_id
    )
    
    message_data = message.to_dict()
    # Emit to both the thread room and the channel
    socketio.emit('message.new', message_data, room=f"thread_{message_id}")
    socketio.emit('message.new', message_data, room=parent_message.channel_id)
    
    return jsonify(message_data), 201

@bp.route('/<message_id>/reactions/<emoji>', methods=['DELETE', 'OPTIONS'])
@cross_origin()
@auth_required
def remove_reaction(message_id, emoji):
    if request.method == 'OPTIONS':
        return '', 200
        
    user_id = request.user_id
    thread_id = request.args.get('thread_id')
    db.remove_reaction(message_id, user_id, emoji, thread_id)
    message = db.get_message(message_id, thread_id=thread_id)
    if not message:
        return jsonify({'error': 'Message not found'}), 404
    return jsonify(message.to_dict())

@bp.route('/<message_id>/reactions', methods=['POST', 'OPTIONS'])
@cross_origin()
@auth_required
def add_reaction(message_id):
    if request.method == 'OPTIONS':
        return '', 200
        
    user_id = request.user_id
    data = request.get_json()
    emoji = data['emoji']
    thread_id = request.args.get('thread_id')
    
    reaction = db.add_reaction(message_id, user_id, emoji, thread_id)
    message = db.get_message(message_id, thread_id=thread_id)
    if not message:
        return jsonify({'error': 'Message not found'}), 404
    
    message_data = message.to_dict()
    socketio.emit('message.reaction', message_data, room=message.channel_id)
    return jsonify(message_data)

@bp.route('/<message_id>')
@cross_origin()
@auth_required
def get_message(message_id):
    thread_id = request.args.get('thread_id')
    message = db.get_message(message_id, thread_id=thread_id)
    if not message:
        return jsonify({'error': 'Message not found'}), 404
    return jsonify(message.to_dict())

@bp.route('/uploads/<filename>')
def serve_file(filename):
    return send_from_directory(os.path.join(os.getcwd(), 'uploads'), filename)

@bp.route('/<message_id>', methods=['PUT', 'OPTIONS'])
@cross_origin()
@auth_required
def update_message(message_id):
    if request.method == 'OPTIONS':
        return '', 200
        
    user_id = request.user_id
    data = request.get_json()
    thread_id = request.args.get('thread_id')
    
    message = db.get_message(message_id, thread_id=thread_id)
    if not message:
        return jsonify({'error': 'Message not found'}), 404
        
    if message.user_id != user_id:
        return jsonify({'error': 'Unauthorized'}), 403
        
    updated_message = db.update_message(message_id, data['content'])
    message_data = updated_message.to_dict()
    socketio.emit('message.update', message_data, room=message.channel_id)
    
    return jsonify(message_data)

@bp.route('/users/<user_id>/messages')
@auth_required
def get_user_messages(user_id):
    """Get messages created by a user."""
    try:
        before = request.args.get('before')  # Optional timestamp for pagination
        limit = request.args.get('limit', 50, type=int)
        if limit < 1 or limit > 100:
            limit = 50
            
        messages = db.get_user_messages(user_id, before, limit)
        return jsonify([msg.to_dict() for msg in messages])
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        print(f"Error getting user messages: {str(e)}")
        return jsonify({'error': 'Failed to get messages'}), 500 