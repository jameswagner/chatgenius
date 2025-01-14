from flask import Blueprint, jsonify, request
from ..services.qa_service import QAService
from flask_cors import cross_origin
from asgiref.sync import async_to_sync

bp = Blueprint('qa', __name__)
qa_service = QAService()

@bp.route('/users/<user_id>/ask', methods=['POST'])
@cross_origin()
def ask_about_user(user_id):
    """Ask a question about a specific user"""
    try:
        data = request.get_json()
        if not data or 'question' not in data:
            return jsonify({"error": "Question is required"}), 400
            
        question = data['question']
        response = async_to_sync(qa_service.ask_about_user)(user_id, question)
        return jsonify(response)
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to process question: {str(e)}"}), 500

@bp.route('/users/email/<email>/ask', methods=['POST'])
@cross_origin()
def ask_about_user_by_email(email):
    """Ask a question about a user by their email"""
    try:
        data = request.get_json()
        if not data or 'question' not in data:
            return jsonify({"error": "Question is required"}), 400
            
        # Get user by email
        user = qa_service.user_service.get_user_by_email(email)
        if not user:
            return jsonify({"error": "User not found"}), 404
            
        question = data['question']
        response = async_to_sync(qa_service.ask_about_user)(user.id, question)
        return jsonify(response)
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to process question: {str(e)}"}), 500

@bp.route('/channels/<channel_id>/ask', methods=['POST'])
@cross_origin()
def ask_about_channel(channel_id):
    """Ask a question about a specific channel"""
    try:
        data = request.get_json()
        if not data or 'question' not in data:
            return jsonify({"error": "Question is required"}), 400
            
        print(f"\n=== Channel QA Request ===")
        print(f"Input channel_id/name: {channel_id}")
            
        # If this looks like a name rather than ID, get the channel by name
        if not channel_id.startswith('CHANNEL#'):
            channel = qa_service.channel_service.get_channel_by_name(channel_id)
            if not channel:
                print(f"❌ No channel found with name: {channel_id}")
                return jsonify({"error": "Channel not found"}), 404
            channel_id = channel.id
            print(f"✓ Found channel: {channel.name} (ID: {channel_id})")
            
        question = data['question']
        print(f"Question: {question}")
        response = async_to_sync(qa_service.ask_about_channel)(channel_id, question)
        return jsonify(response)
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({"error": f"Failed to process question: {str(e)}"}), 500

@bp.route('/channels/name/<name>/ask', methods=['POST'])
@cross_origin()
def ask_about_channel_by_name(name):
    """Ask a question about a channel by its name"""
    try:
        data = request.get_json()
        if not data or 'question' not in data:
            return jsonify({"error": "Question is required"}), 400
            
        # Get channel by name
        channel = qa_service.channel_service.get_channel_by_name(name)
        if not channel:
            return jsonify({"error": "Channel not found"}), 404
            
        question = data['question']
        response = async_to_sync(qa_service.ask_about_channel)(channel.id, question)
        return jsonify(response)
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to process question: {str(e)}"}), 500

@bp.route('/workspaces/<workspace_id>/ask', methods=['POST'])
@cross_origin()
def ask_about_workspace(workspace_id):
    """Ask a question about a workspace"""
    try:
        data = request.get_json()
        if not data or 'question' not in data:
            return jsonify({"error": "Question is required"}), 400
            
        question = data['question']
        response = async_to_sync(qa_service.ask_about_workspace)(workspace_id, question)
        return jsonify(response)
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to process question: {str(e)}"}), 500 