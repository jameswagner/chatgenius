from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime, timezone
from app.db.sqlite import SQLiteDB
from app.auth.auth_service import AuthService, auth_required
import os
import jwt
from werkzeug.utils import secure_filename
from app.storage.file_storage import FileStorage

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
socketio = SocketIO(app, cors_allowed_origins="http://localhost:5173")
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:5173"],
        "allow_headers": ["Content-Type", "Authorization"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    }
})
app.static_folder = 'uploads'  # This tells Flask where to find static files

db = SQLiteDB()
auth_service = AuthService(db, app.config['SECRET_KEY'])

file_storage = FileStorage()
MAX_FILES = 3
MAX_FILE_SIZE = 1024 * 1024  # 1MB

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

@app.route('/auth/logout', methods=['POST'])
@auth_required
def logout():
    try:
        # Set user status to offline on logout
        db.update_user_status(request.user_id, 'offline')
        
        # Emit status change to all connected clients
        socketio.emit('user.status', {
            'userId': request.user_id,
            'status': 'offline',
            'lastActive': datetime.now(timezone.utc).isoformat()
        })
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
            created_by=request.user_id,
            other_user_id=data.get('otherUserId')  # For DM channels
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
    print("Received message creation request")  # Debug
    files = request.files.getlist('files')
    print(f"Files received: {[f.filename for f in files]}")  # Debug file list
    
    # Validate number of files
    if len(files) > MAX_FILES:
        return jsonify({'error': f'Maximum {MAX_FILES} files allowed'}), 400

    # Save files
    saved_files = []
    try:
        for file in files:
            if file.filename:
                print(f"Processing file: {file.filename}")  # Debug each file
                filename = file_storage.save_file(file, MAX_FILE_SIZE)
                print(f"Saved as: {filename}")  # Debug saved filename
                saved_files.append(filename)
    except ValueError as e:
        print(f"Error saving files: {str(e)}")  # Debug errors
        # Clean up any saved files
        for filename in saved_files:
            file_storage.delete_file(filename)
        return jsonify({'error': str(e)}), 400

    # Create message
    data = request.form
    print(f"Form data: {data}")  # Debug form data
    message = db.create_message(
        channel_id=channel_id,
        user_id=request.user_id,
        content=data['content'],
        thread_id=data.get('thread_id'),
        attachments=saved_files
    )
    
    message_data = message.to_dict()
    print(f"Created message: {message_data}")  # Debug created message
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
    message_data = message.to_dict()
    
    # Emit to the channel so all members see the new reply
    socketio.emit('message.new', message_data, room=parent_message.channel_id)
    
    return jsonify(message_data), 201

# WebSocket event handlers
@socketio.on('connect')
def handle_connect():
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            raise ConnectionRefusedError('Authentication required')
            
        token = auth_header.split(' ')[1]
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = payload['sub']
        
        # Store user_id in session for later use
        request.user_id = user_id
        print(f'Client connected: {user_id}')  # Debug log
        
        # Get and broadcast current user status
        user = db.get_user_by_id(user_id)
        if user:
            status_update = {
                'userId': user.id,
                'status': user.status,
                'lastActive': user.to_dict()['lastActive']
            }
            print(f"Broadcasting initial status: {status_update}")  # Debug log
            socketio.emit('user.status', status_update)
            
    except Exception as e:
        print(f"Connection error: {str(e)}")  # Debug log
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

@app.route('/channels/<channel_id>/join', methods=['POST'])
@auth_required
def join_channel(channel_id):
    try:
        db.add_channel_member(channel_id, request.user_id)
        return jsonify({'success': True}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

@app.route('/channels/<channel_id>/leave', methods=['POST'])
@auth_required
def leave_channel(channel_id):
    if channel_id == 'general':
        return jsonify({'error': 'Cannot leave general channel'}), 400
    try:
        db.remove_channel_member(channel_id, request.user_id)
        return jsonify({'success': True}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

@app.route('/channels/available')
@auth_required
def get_available_channels():
    """Get public channels that the user can join"""
    channels = db.get_available_channels(request.user_id)
    return jsonify([channel.to_dict() for channel in channels])

@app.route('/messages/<message_id>/reactions/<emoji>', methods=['DELETE'])
@auth_required
def remove_reaction(message_id, emoji):
    try:
        db.remove_reaction(message_id, request.user_id, emoji)
        # Return updated reactions for the message
        message = db.get_message(message_id)
        return jsonify(message.reactions), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404

@app.route('/messages/<message_id>/reactions', methods=['POST'])
@auth_required
def add_reaction(message_id):
    data = request.get_json()
    try:
        reaction = db.add_reaction(
            message_id=message_id,
            user_id=request.user_id,
            emoji=data['emoji']
        )
        # Get the full message with reactions
        message = db.get_message(message_id)
        message_data = message.to_dict()
        # Emit to the channel so main view updates
        socketio.emit('message.reaction', message_data, room=message.channel_id)
        return jsonify(message.reactions), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

@app.route('/messages/<message_id>')
@auth_required
def get_message(message_id):
    message = db.get_message(message_id)
    if not message:
        return jsonify({'error': 'Message not found'}), 404
    return jsonify(message.to_dict())

@app.route('/users')
@auth_required
def get_users():
    """Get all users except the current user"""
    try:
        users = db.get_all_users()
        # Only return id and name
        return jsonify([{
            'id': user['id'],
            'name': user['name']
        } for user in users if user['id'] != request.user_id])  # Exclude current user
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Add this route to serve uploaded files
@app.route('/uploads/<filename>')
@auth_required
def serve_file(filename):
    """Serve uploaded files using Flask's send_static_file"""
    print(f"[DEBUG] Serve file request received for: {filename}")  # Debug
    print(f"[DEBUG] Static folder is: {app.static_folder}")  # Debug
    print(f"[DEBUG] Current working directory: {os.getcwd()}")  # Debug
    print(f"[DEBUG] Full path would be: {os.path.join(os.getcwd(), app.static_folder, filename)}")  # Debug
    try:
        return app.send_static_file(filename)
    except Exception as e:
        print(f"[DEBUG] Error serving file {filename}: {str(e)}")  # Debug
        return jsonify({'error': 'File not found'}), 404

# Add the new status endpoint
@app.route('/users/status', methods=['PUT'])
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
            'status': data['status'],  # This is the key change
            'lastActive': user_dict['lastActive']
        }
        
        print(f"[STATUS] 4. Emitting status update: {status_update}")
        socketio.emit('user.status', status_update)
        
        return jsonify(user_dict)
    except Exception as e:
        print(f"[STATUS] ERROR: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/users/me')
@auth_required
def get_current_user():
    """Get current user's data"""
    user = db.get_user_by_id(request.user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(user.to_dict())

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=3000, debug=True) 