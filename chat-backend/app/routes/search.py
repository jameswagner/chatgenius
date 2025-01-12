from flask import Blueprint, request, jsonify
from app.auth.auth_service import auth_required
from app.db.ddb import DynamoDB
from flask_cors import cross_origin
import os

bp = Blueprint('search', __name__)
db = DynamoDB(table_name=os.environ.get('DYNAMODB_TABLE', 'chat_app_jrw'))

@bp.route('/messages', methods=['GET', 'OPTIONS'])
@cross_origin()
@auth_required
def search_messages():
    if request.method == 'OPTIONS':
        return '', 200
        
    query = request.args.get('q', '')
    channel_id = request.args.get('channel_id')
    
    if not query:
        return jsonify({'error': 'Search query is required'}), 400
        
    messages = db.search_messages(request.user_id, query)
    
    # Enhance message data with channel info
    response = []
    for message in messages:
        message_data = message.to_dict()
        channel = db.get_channel_by_id(message.channel_id)
        if channel:
            message_data['channel'] = channel.to_dict()
        response.append(message_data)
        
    return jsonify(response) 