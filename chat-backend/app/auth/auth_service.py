import jwt
from datetime import datetime, timezone, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask import request, jsonify, current_app
import logging
from boto3.dynamodb.conditions import Key

class AuthService:
    def __init__(self, db, secret_key):
        self.db = db
        self.secret_key = secret_key

    def decode_token(self, token):
        try:
            logging.info("Decoding token...")
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            logging.info(f"Token decoded successfully for user {payload['sub']}")
            return payload
        except jwt.ExpiredSignatureError:
            logging.error("Token has expired")
            raise ValueError('Token has expired')
        except jwt.InvalidTokenError:
            logging.error("Invalid token format or signature")
            raise ValueError('Invalid token')

    def create_token(self, user_id):
        logging.info(f"Creating token for user {user_id}")
        payload = {
            'sub': user_id,
            'exp': int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp())
        }
        return jwt.encode(payload, self.secret_key, algorithm='HS256')

    def register(self, email: str, password: str, name: str) -> dict:
        logging.info(f"Starting registration for email: {email}")
        
        # Check if user already exists
        existing_user = self.db.get_user_by_email(email)
        if existing_user:
            logging.warning(f"Registration failed: Email {email} already registered")
            raise ValueError(f"Email {email} already registered")
            
        # Create user
        logging.info("Creating new user...")
        user = self.db.create_user(email=email, password=generate_password_hash(password), name=name)
        logging.info(f"Created user with ID: {user.id}")
        
        # Add user to general channel
        try:
            logging.info(f"Adding user {user.id} to general channel...")
            self.db.add_channel_member('general', user.id)
            logging.info("Successfully added user to general channel")
        except Exception as e:
            logging.error(f"Failed to add user to general channel: {str(e)}")
            raise
        
        # Generate tokens
        token = self.create_token(user.id)
        logging.info(f"Registration completed successfully for user {user.id}")
        
        return {
            'token': token,
            'user_id': user.id
        }

    def login(self, email: str, password: str = None):
        """Login a user and return a token
        
        For regular users, both email and password are required.
        For persona users, only email is required.
        """
        logging.info(f"Attempting login for email: {email}")
        
        # Get user by email
        user = self.db.get_user_by_email(email)
        if not user:
            logging.warning(f"Login failed: No user found with email {email}")
            raise ValueError('Invalid email or password')
        print(f"User: {user}")
            
        # Handle persona users (no password required)
        if user.type == 'persona':
            logging.info(f"Logging in persona user {user.id}")
        # Handle regular users (password required)
        else:
            if not password:
                logging.warning(f"Login failed: Password required for non-persona user {user.id}")
                raise ValueError('Password is required')
                
            if not check_password_hash(user.password, password):
                logging.warning(f"Login failed: Invalid password for user {user.id}")
                raise ValueError('Invalid email or password')
            
            logging.info(f"Password verified for user {user.id}")
            
        # Set user status to online
        logging.info(f"Updating status to online for user {user.id}")
        user = self.db.update_user_status(user.id, 'online')
        
        # Generate token
        token = self.create_token(user.id)
        logging.info(f"Login successful for user {user.id}")
        
        return {
            'token': token,
            'user': user.to_dict()
        }

    def logout(self, user_id: str):
        """Logout a user by setting their status to offline"""
        logging.info(f"Logging out user {user_id}")
        try:
            user = self.db.update_user_status(user_id, 'offline')
            logging.info(f"Successfully logged out user {user_id}")
            return user
        except Exception as e:
            logging.error(f"Failed to logout user {user_id}: {str(e)}")
            raise

def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            logging.warning("Request missing Authorization header or invalid format")
            return jsonify({'error': 'No token provided'}), 401

        try:
            token = auth_header.split(' ')[1]
            logging.info("Validating token...")
            payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            request.user_id = payload['sub']
            logging.info(f"Token valid for user {request.user_id}")
            return f(*args, **kwargs)
        except jwt.ExpiredSignatureError:
            logging.error("Token validation failed: Token has expired")
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            logging.error("Token validation failed: Invalid token")
            return jsonify({'error': 'Invalid token'}), 401

    return decorated 