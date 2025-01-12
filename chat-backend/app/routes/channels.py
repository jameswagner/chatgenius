from flask import Blueprint, request, jsonify
from app.auth.auth_service import auth_required
from app.db.ddb import DynamoDB
from app import get_socketio
from flask_socketio import emit, join_room, leave_room
from werkzeug.utils import secure_filename
from app.storage.file_storage import FileStorage
import os
from datetime import datetime, timezone
import uuid
import logging

bp = Blueprint('channels', __name__)
db = DynamoDB(table_name=os.environ.get('DYNAMODB_TABLE', 'chat_app_jrw'))
socketio = get_socketio()
file_storage = FileStorage()

@bp.route('', defaults={'trailing_slash': ''})
@bp.route('/')
@auth_required
def get_channels():
    channels = db.get_channels_for_user(request.user_id)
    return jsonify([channel.to_dict() for channel in channels])

@bp.route('', methods=['POST'], defaults={'trailing_slash': ''})
@bp.route('/', methods=['POST'])
@auth_required
def create_channel():
    user_id = request.user_id
    data = request.get_json()
    
    # Validate required fields
    if not data or not data.get('name'):
        return jsonify({'error': 'Channel name is required'}), 400
        
    try:
        # For DM channels, check if one already exists
        if data.get('type') == 'dm' and data.get('otherUserId'):
            existing_channel = db.get_dm_channel(user_id, data['otherUserId'])
            if existing_channel:
                return jsonify(existing_channel.to_dict()), 200

        # Create new channel
        channel = db.create_channel(
            name=data['name'],
            type=data.get('type', 'public'),
            created_by=user_id,
            other_user_id=data.get('otherUserId')
        )
        
        # Only emit for non-DM channels
        # For DMs, we'll emit when the first message is sent
        if data.get('type') != 'dm':
            socketio.emit('channel.new', channel.to_dict())
            
        return jsonify(channel.to_dict()), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Failed to create channel'}), 500

@bp.route('/<channel_id>/join', methods=['POST'])
@auth_required
def join_channel(channel_id):
    try:
        # Check if channel exists
        channel = db.get_channel_by_id(channel_id)
        if not channel:
            return jsonify({'error': 'Channel not found'}), 404
            
        # Check if it's a DM channel
        if channel.type == 'dm':
            return jsonify({'error': 'Cannot join DM channels directly'}), 400
            
        # Add member to channel
        db.add_channel_member(channel_id, request.user_id)
        
        # Join the socket room
        socketio.emit('channel.member.joined', {
            'channelId': channel_id,
            'userId': request.user_id
        })
        
        return jsonify({'success': True}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Failed to join channel'}), 500

@bp.route('/<channel_id>/leave', methods=['POST'])
@auth_required
def leave_channel(channel_id):
    try:
        # Check if channel exists
        channel = db.get_channel_by_id(channel_id)
        if not channel:
            return jsonify({'error': 'Channel not found'}), 404
            
        # Cannot leave general channel
        if channel_id == 'general':
            return jsonify({'error': 'Cannot leave general channel'}), 400
            
        # Cannot leave DM channels
        if channel.type == 'dm':
            return jsonify({'error': 'Cannot leave DM channels'}), 400
            
        # Remove member from channel
        db.remove_channel_member(channel_id, request.user_id)
        
        # Emit member left event
        socketio.emit('channel.member.left', {
            'channelId': channel_id,
            'userId': request.user_id
        })
        
        return jsonify({'success': True}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Failed to leave channel'}), 500

@bp.route('/available')
@auth_required
def get_available_channels():
    try:
        # Get all channels the user can join
        channels = db.get_available_channels(request.user_id)
        
        # Filter out DM channels
        channels = [c for c in channels if c.type != 'dm']
        
        return jsonify([channel.to_dict() for channel in channels])
    except Exception as e:
        return jsonify({'error': 'Failed to get available channels'}), 500

@bp.route('/<channel_id>/read', methods=['POST'])
@auth_required
def mark_channel_read(channel_id):
    try:
        # Check if channel exists
        channel = db.get_channel_by_id(channel_id)
        if not channel:
            return jsonify({'error': 'Channel not found'}), 404
            
        # Check if user is member of channel
        if not db.is_channel_member(channel_id, request.user_id):
            return jsonify({'error': 'Not a member of this channel'}), 403
            
        # Mark channel as read
        try:
            db.mark_channel_read(channel_id, request.user_id)
        except Exception as e:
            logging.error(f"Error in mark_channel_read: {str(e)}")
            logging.error(f"Error type: {type(e)}")
            raise
        
        return jsonify({'success': True})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logging.error(f"Outer error in mark_channel_read route: {str(e)}")
        logging.error(f"Outer error type: {type(e)}")
        return jsonify({'error': 'Failed to mark channel as read'}), 500

@bp.route('/<channel_id>/messages')
@auth_required
def get_channel_messages(channel_id):
    before = request.args.get('before')
    limit = int(request.args.get('limit', 50))
    messages = db.get_messages(channel_id, before=before, limit=limit)
    if messages is None:
        return jsonify({'error': 'Failed to get messages'}), 500
    return jsonify([message.to_dict() for message in messages])

@bp.route('/<channel_id>/messages', methods=['POST'])
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
                        
                        # Use direct upload folder path
                        upload_folder = 'uploads'
                        save_path = os.path.join(upload_folder, saved_filename)
                        print(f"Saving to: {save_path}")
                        
                        # Ensure upload directory exists
                        os.makedirs(upload_folder, exist_ok=True)
                        
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

@bp.route('/uploads/<filename>')
def serve_file(filename):
    """Generate a presigned URL for the file"""
    try:
        url = file_storage.get_file_url(filename)
        return jsonify({'url': url}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404

# Socket.IO event handlers
@socketio.on('channel.join')
def handle_join_channel(channel_id):
    join_room(channel_id)
    
@socketio.on('channel.leave')
def handle_leave_channel(channel_id):
    leave_room(channel_id) 