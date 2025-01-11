from flask import Blueprint, request, jsonify
from ..auth.auth_service import AuthService
from ..db.ddb import DynamoDB
from flask import current_app

auth_bp = Blueprint('auth', __name__)
db = DynamoDB()
auth_service = AuthService(db, current_app.config['SECRET_KEY'])

@auth_bp.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        result = auth_service.register(
            email=data['email'],
            password=data['password'],
            name=data['name']
        )
        return jsonify(result), 201
    except ValueError as e:
        print(f"Error registering user: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        print(f"Error registering user: {e}")
        return jsonify({'error': 'Registration failed'}), 500

@auth_bp.route('/personas/login', methods=['POST'])
def login_as_persona():
    """Login as a persona user"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if 'email' not in data:
            return jsonify({'error': 'Missing email'}), 400
            
        # Try to login as persona
        result = auth_service.login_as_persona(data['email'])
        return jsonify(result), 200
        
    except ValueError as e:
        print(f"Persona login failed: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return jsonify({'error': 'Login failed'}), 500

@auth_bp.route('/login', methods=['POST'])
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
    except Exception as e:
        return jsonify({'error': 'Login failed'}), 500 