import jwt
from datetime import datetime, timezone, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask import request, jsonify, current_app

class AuthService:
    def __init__(self, db, secret_key):
        self.db = db
        self.secret_key = secret_key

    def decode_token(self, token):
        try:
            return jwt.decode(token, self.secret_key, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            raise ValueError('Token has expired')
        except jwt.InvalidTokenError:
            raise ValueError('Invalid token')

    def create_token(self, user_id):
        payload = {
            'sub': user_id,
            'exp': int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp())
        }
        return jwt.encode(payload, self.secret_key, algorithm='HS256')

    def register(self, email: str, password: str, name: str) -> dict:
        # Check if user already exists
        if self.db.get_user_by_email(email):
            raise ValueError(f"Email {email} already registered")
            
        # Create user
        user = self.db.create_user(email=email, password=generate_password_hash(password), name=name)
        
        # Add user to general channel
        try:
            self.db.add_channel_member('general', user.id)
        except Exception as e:
            print(f"Error adding user to general channel: {e}")
        
        # Generate tokens
        token = self.create_token(user.id)
        
        return {
            'token': token,
            'user_id': user.id
        }

    def login(self, email: str, password: str):
        """Login a user and return a token"""
        user = self.db.get_user_by_email(email)
        if not user or not check_password_hash(user.password, password):
            raise ValueError('Invalid email or password')
            
        # Set user status to online on login
        user = self.db.update_user_status(user.id, 'online')
        
        token = self.create_token(user.id)
        return {
            'token': token,
            'user_id': user.id
        } 

def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'No token provided'}), 401

        try:
            token = auth_header.split(' ')[1]
            payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            request.user_id = payload['sub']
            return f(*args, **kwargs)
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401

    return decorated 