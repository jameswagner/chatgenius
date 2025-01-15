from flask import Blueprint, request, jsonify, current_app
from app.auth.auth_service import AuthService, auth_required
from app.db.ddb import DynamoDB
import os
import logging

bp = Blueprint('auth', __name__)
db = DynamoDB(table_name=os.environ.get('DYNAMODB_TABLE', 'chat_app_jrw'))

def get_auth_service():
    return AuthService(db=db, secret_key=current_app.config['SECRET_KEY'])

@bp.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        
        # Validate required fields
        if not all(k in data for k in ['email', 'password', 'name']):
            return jsonify({'error': 'Missing required fields'}), 400
            
        # Try to register
        auth_service = get_auth_service()
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

@bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        logging.info(f"Login request received for email: {data.get('email')}")
        auth_service = get_auth_service()
        result = auth_service.login(
            email=data['email'],
            password=data['password']
        )
        logging.info(f"Login successful, response: {result}")
        logging.debug(f"Detailed response: {result}")
        return jsonify(result)
    except ValueError as e:
        logging.error(f"Login failed: {str(e)}")
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        logging.error(f"Unexpected error during login: {str(e)}")
        return jsonify({'error': 'Login failed'}), 500

@bp.route('/me')
@auth_required
def get_current_user():
    user_id = request.user_id
    user = db.get_user_by_id(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(user.to_dict())

@bp.route('/users/<user_id>')
@auth_required
def get_user(user_id):
    user = db.get_user_by_id(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(user.to_dict())

@bp.route('/users/status', methods=['PUT'])
@auth_required
def update_status():
    user_id = request.user_id
    data = request.get_json()
    
    user = db.get_user_by_id(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
        
    user = db.update_user_status(user_id, data['status'])
    
    return jsonify(user.to_dict())

@bp.route('/users/search')
@auth_required
def search_users():
    query = request.args.get('q', '')
    if not query:
        return jsonify({'error': 'Search query is required'}), 400
        
    users = db.search_users(query)
    return jsonify([user.to_dict() for user in users]) 

@bp.route('/logout', methods=['OPTIONS', 'POST'])
def logout():
    if request.method == 'OPTIONS':
        return '', 200
        
    @auth_required
    def handle_logout():
        try:
            auth_service = get_auth_service()
            auth_service.logout(request.user_id)
            return jsonify({'message': 'Logged out successfully'})
        except Exception as e:
            logging.error(f"Error during logout: {str(e)}")
            return jsonify({'error': 'Logout failed'}), 500
            
    return handle_logout() 

@bp.route('/users/name/<name>')
@auth_required
def get_user_by_name(name):
    """Get a user by their username."""
    user = db.get_user_by_name(name)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(user.to_dict()) 