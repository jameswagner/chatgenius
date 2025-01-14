from flask import Blueprint, jsonify, request
from ..services.vector_service import VectorService
from ..services.user_service import UserService
from ..services.channel_service import ChannelService
from flask_cors import cross_origin
from asgiref.sync import async_to_sync

bp = Blueprint('vector', __name__)
vector_service = VectorService()
user_service = UserService()
channel_service = ChannelService()

@bp.route('/users/<user_id>/index', methods=['POST'])
@cross_origin()
def index_user(user_id):
    """Index a user's profile in the vector database"""
    try:
        result = async_to_sync(vector_service.index_user)(user_id)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/users/email/<email>/index', methods=['POST']) 
@cross_origin()
def index_user_by_email(email):
    """Index a user's profile by email"""
    try:
        user = user_service.get_user_by_email(email)
        if not user:
            return jsonify({"error": f"User with email '{email}' not found"}), 404
            
        result = async_to_sync(vector_service.index_user)(user.id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/channels/<name>/index', methods=['POST'])
@cross_origin()
def index_channel_by_name(name):
    """Index a channel's messages by channel name"""
    try:
        channel = channel_service.get_channel_by_name(name)
        if not channel:
            return jsonify({"error": f"Channel '{name}' not found"}), 404
            
        result = async_to_sync(vector_service.index_channel)(channel.id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/search', methods=['GET'])
@cross_origin()
def search_similar():
    """Search for similar content across messages and profiles"""
    try:
        query = request.args.get('query')
        if not query:
            return jsonify({"error": "Query parameter is required"}), 400
            
        doc_type = request.args.get('type', 'all')
        if doc_type not in ['message', 'user_profile', 'all']:
            return jsonify({"error": "Invalid document type"}), 400
            
        limit = request.args.get('limit', default=10, type=int)
        
        results = async_to_sync(vector_service.search_similar)(
            query=query,
            doc_type=doc_type,
            limit=limit
        )
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/users/<user_id>/context', methods=['GET'])
@cross_origin()
def get_user_context(user_id):
    """Get a user's context including profile and messages"""
    try:
        include_profile = request.args.get('include_profile', default='true').lower() == 'true'
        context = async_to_sync(vector_service.get_user_context)(
            user_id=user_id,
            include_profile=include_profile
        )
        return jsonify(context)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/users/email/<email>/context', methods=['GET'])
@cross_origin()
def get_user_context_by_email(email):
    """Get a user's context by email"""
    try:
        user = user_service.get_user_by_email(email)
        if not user:
            return jsonify({"error": f"User with email '{email}' not found"}), 404
            
        include_profile = request.args.get('include_profile', default='true').lower() == 'true'
        context = async_to_sync(vector_service.get_user_context)(
            user_id=user.id,
            include_profile=include_profile
        )
        return jsonify(context)
    except Exception as e:
        return jsonify({"error": str(e)}), 500 

@bp.route('/workspaces/<workspace_id>/index', methods=['POST'])
@cross_origin()
def index_workspace(workspace_id):
    """Index all channels and their members in a workspace"""
    try:
        print(f"\nIndexing workspace {workspace_id}...")
        
        # Get date range parameters
        start_date = request.args.get('start_date')  # Format: YYYY-MM-DD
        end_date = request.args.get('end_date')      # Format: YYYY-MM-DD
        
        date_range = ""
        if start_date and end_date:
            date_range = f" (messages from {start_date} to {end_date})"
        elif start_date:
            date_range = f" (messages from {start_date})"
        elif end_date:
            date_range = f" (messages until {end_date})"
            
        # Get all channels in workspace
        channels = channel_service.get_workspace_channels(workspace_id)
        if not channels:
            return jsonify({"error": f"No channels found in workspace '{workspace_id}'"}), 404
            
        print(f"Found {len(channels)} channels{date_range}")
        
        # Track unique users who are members of channels in this workspace
        workspace_users = set()
        
        # Index each channel and its messages
        channels_indexed = 0
        messages_indexed = 0
        for channel in channels:
            try:
                # Index channel messages
                print(f"Indexing channel {channel.name}...")
                result = async_to_sync(vector_service.index_channel)(
                    channel.id,
                    start_date=start_date,
                    end_date=end_date
                )
                messages_indexed += result
                print(f"✓ Indexed {result} messages")
                
                # Track channel members
                members = channel_service.get_channel_members(channel.id)
                for member in members:
                    workspace_users.add(member['id'])  # member is a dict with 'id' field
                    
                channels_indexed += 1
            except Exception as e:
                print(f"✗ Failed to index channel {channel.name}: {str(e)}")
            
        print(f"\nFound {len(workspace_users)} unique users")
        
        # Index user profiles for workspace members
        users_indexed = 0
        for user_id in workspace_users:
            try:
                user = user_service.get_user_by_id(user_id)
                if user:
                    print(f"Indexing user {user.email}...")
                    async_to_sync(vector_service.index_user)(user.id)
                    users_indexed += 1
                    print("✓ Indexed user profile")
            except Exception as e:
                print(f"✗ Failed to index user {user_id}: {str(e)}")
                
        print(f"\nIndexing complete!")
        print(f"Channels indexed: {channels_indexed}")
        print(f"Messages indexed: {messages_indexed}")
        print(f"Users indexed: {users_indexed}")
                
        return jsonify({
            "channels_indexed": channels_indexed,
            "messages_indexed": messages_indexed,
            "users_indexed": users_indexed
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500 