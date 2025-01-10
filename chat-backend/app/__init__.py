from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from flask_socketio import SocketIO
import os

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.static_folder = 'uploads'  # This tells Flask where to find static files

# Setup CORS
socketio = SocketIO(app, cors_allowed_origins="http://localhost:5173")
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:5173"],
        "allow_headers": ["Content-Type", "Authorization"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    }
})

# Import routes after app is created to avoid circular imports
from app import routes
