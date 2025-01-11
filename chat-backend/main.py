from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime, timezone
from app.db.ddb import DynamoDB
from app.auth.auth_service import AuthService, auth_required
import os
import jwt
from werkzeug.utils import secure_filename
from app.storage.file_storage import FileStorage
from scripts.create_table import create_chat_table
from boto3.dynamodb.conditions import Key
from boto3 import client
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['DYNAMODB_TABLE'] = os.environ.get('DYNAMODB_TABLE', 'chat_app_jrw')

socketio = SocketIO(app, cors_allowed_origins=["http://localhost:5173", "http://localhost:5174"])
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:5173", "http://localhost:5174"],
        "allow_headers": ["Content-Type", "Authorization"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    }
})
app.static_folder = 'uploads'  # This tells Flask where to find static files

db = DynamoDB(table_name=app.config['DYNAMODB_TABLE'])

# Create table if it doesn't exist
create_chat_table(table_name=app.config['DYNAMODB_TABLE'])

auth_service = AuthService(db, app.config['SECRET_KEY'])

file_storage = FileStorage()
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

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
        # For DM channels, check if one already exists
        if data.get('type') == 'dm' and data.get('otherUserId'):
            existing_channel = db.get_dm_channel(request.user_id, data['otherUserId'])
            if existing_channel:
                return jsonify(existing_channel.to_dict()), 200

        # If no existing DM found, or not a DM, create new channel
        channel = db.create_channel(
            name=data['name'],
            type=data.get('type', 'public'),
            created_by=request.user_id,
            other_user_id=data.get('otherUserId')
        )
        
        # Only emit for non-DM channels
        # For DMs, we'll emit when the first message is sent
        if data.get('type') != 'dm':
            socketio.emit('channel.new', channel.to_dict())
            
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
    try:
        print("\n=== Creating Message with Attachments ===")
        content = request.form.get('content', '')
        thread_id = request.form.get('thread_id')
        files = request.files.getlist('files')
        
        print(f"Content: {content}")
        print(f"Thread ID: {thread_id}")
        print(f"Number of files: {len(files)}")
        
        attachments = []

        # Process file uploads
        if files:
            print("\nProcessing files:")
            for file in files:
                if file.filename:
                    try:
                        print(f"\nProcessing file: {file.filename}")
                        filename = secure_filename(file.filename)
                        saved_filename = str(uuid.uuid4().hex[:8]) + '.' + filename.rsplit('.', 1)[1].lower()
                        print(f"Secured filename: {saved_filename}")
                        
                        # Check if UPLOAD_FOLDER is configured
                        if not app.config.get('UPLOAD_FOLDER'):
                            print("WARNING: UPLOAD_FOLDER not configured!")
                            app.config['UPLOAD_FOLDER'] = 'uploads'
                            
                        save_path = os.path.join(app.config['UPLOAD_FOLDER'], saved_filename)
                        print(f"Saving to: {save_path}")
                        
                        # Ensure upload directory exists
                        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                        
                        file.save(save_path)
                        print(f"File saved successfully locally")
                        
                        # Upload to S3
                        print(f"Uploading to S3...")
                        with open(save_path, 'rb') as f:
                            if file_storage.save_file(f, saved_filename):
                                print(f"File uploaded to S3 successfully")
                                attachments.append(saved_filename)
                                # Clean up local file
                                os.remove(save_path)
                                print(f"Local file cleaned up")
                            else:
                                print(f"Failed to upload file to S3")
                                raise Exception("Failed to upload file to S3")
                    except Exception as e:
                        print(f"Error handling file: {str(e)}")
                        print(f"Error type: {type(e)}")
                        # Clean up local file if it exists
                        if os.path.exists(save_path):
                            os.remove(save_path)
                            print(f"Cleaned up local file after error")
                else:
                    print("Skipping file with no filename")

        print(f"\nFinal attachments list: {attachments}")

        # Create message
        message = db.create_message(
            channel_id=channel_id,
            content=content,
            user_id=request.user_id,
            thread_id=thread_id,
            attachments=attachments
        )
        
        message_data = message.to_dict()
        print(f"\nCreated message: {message_data}")
        
        # Get channel info to check if it's a DM and emit channel.new if it's the first message
        channel = db.get_channel_by_id(channel_id)
        if channel and channel.type == 'dm':
            # Get all messages in channel to check if this is the first one
            messages = db.get_messages(channel_id)
            if len(messages) == 1:  # This is the first message
                print("First message in DM channel, emitting channel.new")
                # Get channel with members for proper name display
                channel.members = db.get_channel_members(channel_id)
                print(f"Emitting channel with members: {channel.members}")
                socketio.emit('channel.new', channel.to_dict())
        
        socketio.emit('message.new', message_data, room=channel_id)
        return jsonify(message_data)

    except Exception as e:
        print(f"\nError creating message: {str(e)}")
        print(f"Error type: {type(e)}")
        return jsonify({'error': str(e)}), 500

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
            print('[SOCKET] Connection rejected - no auth header')
            raise ConnectionRefusedError('Authentication required')
            
        token = auth_header.split(' ')[1]
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = payload['sub']
        
        # Store user_id in session for later use
        request.user_id = user_id
        
        # Join user to their personal room for DM notifications
        join_room(user_id)
        print(f'[SOCKET] Client {user_id} connected and joined personal room')
            
    except Exception as e:
        print(f"[SOCKET] Connection error: {str(e)}")
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
def serve_file(filename):
    """Generate a presigned URL for the file"""
    try:
        url = file_storage.get_file_url(filename)
        return jsonify({'url': url}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404

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

@app.route('/search/messages', methods=['GET', 'OPTIONS'])
def search_messages():
    # Handle OPTIONS request for CORS
    if request.method == 'OPTIONS':
        return '', 200
        
    # For GET requests, use the auth decorator
    @auth_required
    def handle_search():
        query = request.args.get('q')
        if not query:
            return jsonify({'error': 'Search query is required'}), 400
            
        try:
            messages = db.search_messages(request.user_id, query)
            return jsonify([message.to_dict() for message in messages])
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
            
    if request.method == 'GET':
        return handle_search()

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'service': 'jrw-chat-app'
    }), 200

@app.route('/messages/<message_id>', methods=['PUT'])
@auth_required
def update_message(message_id):
    data = request.get_json()
    
    if not data or 'content' not in data:
        return jsonify({'error': 'Content is required'}), 400
    
    try:
        # Get the message
        message = db.get_message(message_id)
        if not message:
            return jsonify({'error': 'Message not found'}), 404
        
        # Verify ownership
        if str(message.user_id) != str(request.user_id):
            return jsonify({'error': 'You can only edit your own messages'}), 403
        
        # Update the message
        updated_message = db.update_message(
            message_id=message_id,
            content=data['content']
        )
        
        # Emit WebSocket event
        socketio.emit('message.update', updated_message.to_dict(), room=str(message.channel_id))
        
        return jsonify(updated_message.to_dict())

    except Exception as e:
        print(f"Error updating message: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/channels/<channel_id>/read', methods=['POST'])
@auth_required
def mark_channel_read(channel_id):
    try:
        db.mark_channel_read(channel_id, request.user_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/personas', methods=['GET'])
def get_personas():
    """Get all available personas"""
    try:
        personas = db.get_persona_users()
        return jsonify([p.to_dict() for p in personas]), 200
    except Exception as e:
        print(f"Error getting personas: {e}")
        return jsonify({'error': 'Failed to get personas'}), 500

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True) 