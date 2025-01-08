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
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': 'Registration failed'}), 500

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