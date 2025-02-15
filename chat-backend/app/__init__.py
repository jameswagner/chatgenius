from flask import Flask, request
from flask_cors import CORS
from flask_socketio import SocketIO
import os

socketio = SocketIO()

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    app.config['DYNAMODB_TABLE'] = os.environ.get('DYNAMODB_TABLE', 'chat_app_jrw')
    
    # Initialize CORS
    CORS(app, resources={
        r"/*": {
            "origins": "*",
            "allow_headers": ["Content-Type", "Authorization"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
        }
    })
    
    # Initialize SocketIO
    socketio.init_app(app, cors_allowed_origins="*")
    
    # Register blueprints
    from app.routes import channels, health, auth, messages, users, uploads, search, vector, qa, user_profile
    from .routes.workspace_routes import bp as workspace_bp
    app.register_blueprint(user_profile.user_profile_bp, url_prefix='/user_profile')
    app.register_blueprint(channels.bp, url_prefix='/channels')
    app.register_blueprint(health.bp)
    app.register_blueprint(auth.bp, url_prefix='/auth')
    app.register_blueprint(messages.bp, url_prefix='/messages')
    app.register_blueprint(users.bp, url_prefix='/users')
    app.register_blueprint(uploads.bp, url_prefix='/uploads')
    app.register_blueprint(search.bp, url_prefix='/search')
    app.register_blueprint(vector.bp, url_prefix='/vector')
    app.register_blueprint(qa.bp, url_prefix='/qa')

    
    app.register_blueprint(workspace_bp)
    

    return app

def get_socketio():
    return socketio
