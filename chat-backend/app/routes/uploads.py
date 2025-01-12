from flask import Blueprint, jsonify
from app.storage.file_storage import FileStorage
import os

bp = Blueprint('uploads', __name__)
file_storage = FileStorage()

@bp.route('/<filename>')
def serve_file(filename):
    """Generate a presigned URL for the file"""
    try:
        url = file_storage.get_file_url(filename)
        return jsonify({'url': url}), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404 