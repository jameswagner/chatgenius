from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime, timezone
from app.db.sqlite import SQLiteDB
from app.auth.auth_service import AuthService, auth_required
import os
import jwt

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
socketio = SocketIO(app, cors_allowed_origins="http://localhost:5173")
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:5173"],
        "allow_headers": ["Content-Type", "Authorization"],
        "methods": ["GET", "POST", "OPTIONS"]
    }
})

db = SQLiteDB()
auth_service = AuthService(db, app.config['SECRET_KEY'])

# Auth routes
@app.route('/auth/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        
        # Validate required fields
        if not all(k in data for k in ['email', 'password', 'name']):
            return jsonify({'error': 'Missing required fields'}), 400
            
        # Try to register
        result = auth_service.register(
            email=data['email'],
            password=data['password'],
            name=data['name']
        )
        
        print(f"Registration successful: {result}")  # Debug log
        return jsonify(result), 201
        
    except ValueError as e:
        print(f"Registration failed: {str(e)}")  # Debug log
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        print(f"Unexpected error: {str(e)}")  # Debug log
        return jsonify({'error': 'Registration failed'}), 500

@app.route('/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        result = auth_service.login(
            email=data['email'],
            password=data['password']
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 401

# Channel routes
@app.route('/channels')
@auth_required
def get_channels():
    channels = db.get_channels_for_user(request.user_id)
    return jsonify([channel.to_dict() for channel in channels])

@app.route('/channels', methods=['POST'])
@auth_required
def create_channel():
    data = request.get_json()
    try:
        channel = db.create_channel(
            name=data['name'],
            type=data.get('type', 'public'),
            created_by=request.user_id
        )
        return jsonify(channel.to_dict()), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

# Message routes
@app.route('/channels/<channel_id>/messages')
@auth_required
def get_messages(channel_id):
    messages = db.get_messages(channel_id)
    return jsonify([message.to_dict() for message in messages])

@app.route('/channels/<channel_id>/messages', methods=['POST'])
@auth_required
def create_message(channel_id):
    data = request.get_json()
    message = db.create_message(
        channel_id=channel_id,
        user_id=request.user_id,
        content=data['content'],
        thread_id=data.get('thread_id')
    )
    message_data = message.to_dict()
    socketio.emit('message.new', message_data, room=channel_id)
    return jsonify(message_data), 201

# Thread routes
@app.route('/messages/<message_id>/thread')
@auth_required
def get_thread_messages(message_id):
    messages = db.get_thread_messages(message_id)
    return jsonify([message.to_dict() for message in messages])

@app.route('/messages/<message_id>/thread', methods=['POST'])
@auth_required
def create_thread_reply(message_id):
    data = request.get_json()
    # Get the parent message to get its channel_id
    parent_message = db.get_message(message_id)
    if not parent_message:
        return jsonify({'error': 'Parent message not found'}), 404
        
    message = db.create_message(
        channel_id=parent_message.channel_id,  # Use parent message's channel_id
        user_id=request.user_id,
        content=data['content'],
        thread_id=message_id
    )
    return jsonify(message.to_dict()), 201

# WebSocket event handlers
@socketio.on('connect')
def handle_connect():
    try:
        # Get token from request header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            raise ConnectionRefusedError('Authentication required')
            
        token = auth_header.split(' ')[1]
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        request.user_id = payload['sub']
        print(f'Client connected: {request.user_id}')
    except Exception as e:
        raise ConnectionRefusedError(str(e))

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('channel.join')
def handle_join_channel(channel_id):
    join_room(channel_id)
    print(f'Client joined channel: {channel_id}')

@socketio.on('channel.leave')
def handle_leave_channel(channel_id):
    leave_room(channel_id)
    print(f'Client left channel: {channel_id}')

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=3000, debug=True) 