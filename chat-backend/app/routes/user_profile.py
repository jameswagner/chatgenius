from flask import Blueprint, request, jsonify
from app.db.ddb import create_user_profile, update_all_personas, update_user_profile

user_profile_bp = Blueprint('user_profile', __name__, url_prefix='/user_profile')

@user_profile_bp.route('/user/<user_id>/profile', methods=['POST'])
def create_user_profile_route(user_id):
    profile_data = request.json
    user_profile = create_user_profile(user_id, profile_data)
    return jsonify(user_profile.to_dict()), 201

@user_profile_bp.route('/user/<user_id>/profile', methods=['PUT'])
def update_user_profile_route(user_id):
    update_user_profile(user_id)
    return jsonify({'message': 'User profile updated successfully'}), 200 

@user_profile_bp.route('/update_all_personas', methods=['POST'])
def update_all_personas_route():
    """Endpoint to update all persona profiles."""
    update_all_personas()
    return jsonify({"message": "All persona profiles updated."}), 200 