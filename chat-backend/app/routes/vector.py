from flask import Blueprint, jsonify, request
from ..services.vector_service import VectorService
from ..services.user_service import UserService
from ..services.channel_service import ChannelService
from flask_cors import cross_origin
from asgiref.sync import async_to_sync
from datetime import datetime

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
    """Index a channel's messages by channel name with optional parameters"""
    try:
        channel = channel_service.get_channel_by_name(name)
        if not channel:
            return jsonify({"error": f"Channel '{name}' not found"}), 404

        start_date = request.json.get('start_date')
        end_date = request.json.get('end_date')
        is_grouped = request.json.get('is_grouped', False)

        # Convert date strings to datetime objects
        start_date = datetime.fromisoformat(start_date) if start_date else None
        end_date = datetime.fromisoformat(end_date) if end_date else None

        async_to_sync(vector_service.index_channel)(channel.id, start_date, end_date, is_grouped)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
    """Index a workspace's channels with optional parameters"""
    try:
        start_date = request.json.get('start_date')
        end_date = request.json.get('end_date')
        is_grouped = request.json.get('is_grouped', False)

        # Convert date strings to datetime objects
        start_date = datetime.fromisoformat(start_date) if start_date else None
        end_date = datetime.fromisoformat(end_date) if end_date else None

        async_to_sync(vector_service.index_workspace)(workspace_id, start_date, end_date, is_grouped)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/workspaces/index', methods=['POST'])
@cross_origin()
def index_all_workspaces():
    """Index all workspaces with optional start and end dates"""
    try:
        start_date = request.json.get('start_date')
        end_date = request.json.get('end_date')
        is_grouped = request.json.get('is_grouped', False)

        # Convert date strings to datetime objects
        start_date = datetime.fromisoformat(start_date) if start_date else None
        end_date = datetime.fromisoformat(end_date) if end_date else None

        async_to_sync(vector_service.index_all_workspaces)(start_date, end_date, is_grouped)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500 