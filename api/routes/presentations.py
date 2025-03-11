# api/routes/presentations.py
from flask import Blueprint, request, jsonify, session, redirect, url_for
from google.oauth2.credentials import Credentials
from models.presentation import Presentation, db
from services.presentation_service import PresentationService
import json
import logging

# Create blueprint
presentations_bp = Blueprint('presentations', __name__, url_prefix='/api/presentations')
logger = logging.getLogger(__name__)

# Initialize services
presentation_service = PresentationService()

@presentations_bp.route('/', methods=['GET'])
def get_presentations():
    """Get all presentations for the current user"""
    # Check if user is authenticated
    if 'credentials' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Get user info from credentials
    user_info = session.get('user_info', {})
    user_id = user_info.get('id')
    
    if not user_id:
        return jsonify({'error': 'User ID not found'}), 400
    
    # Query presentations for this user
    presentations = Presentation.query.filter_by(user_id=user_id).order_by(Presentation.created_at.desc()).all()
    
    # Convert to dict for JSON response
    result = [presentation.to_dict() for presentation in presentations]
    
    return jsonify(result)

@presentations_bp.route('/<int:presentation_id>', methods=['GET'])
def get_presentation(presentation_id):
    """Get a single presentation by ID"""
    # Check if user is authenticated
    if 'credentials' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Get user info from credentials
    user_info = session.get('user_info', {})
    user_id = user_info.get('id')
    
    if not user_id:
        return jsonify({'error': 'User ID not found'}), 400
    
    # Query the presentation
    presentation = Presentation.query.filter_by(id=presentation_id, user_id=user_id).first()
    
    if not presentation:
        return jsonify({'error': 'Presentation not found'}), 404
    
    return jsonify(presentation.to_dict())

@presentations_bp.route('/', methods=['POST'])
def create_presentation():
    """Create a new presentation from uploaded CSV file"""
    # Check if user is authenticated
    if 'credentials' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Get user credentials
    credentials_dict = session.get('credentials', {})
    credentials = Credentials(
        token=credentials_dict.get('token'),
        refresh_token=credentials_dict.get('refresh_token'),
        token_uri=credentials_dict.get('token_uri'),
        client_id=credentials_dict.get('client_id'),
        client_secret=credentials_dict.get('client_secret'),
        scopes=credentials_dict.get('scopes')
    )
    
    # Get user info
    user_info = session.get('user_info', {})
    user_id = user_info.get('id')
    
    if not user_id:
        return jsonify({'error': 'User ID not found'}), 400
    
    # Check if CSV file is uploaded
    if 'csv_file' not in request.files:
        return jsonify({'error': 'No CSV file uploaded'}), 400
    
    csv_file = request.files['csv_file']
    
    if csv_file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Check file extension
    if not csv_file.filename.endswith('.csv'):
        return jsonify({'error': 'Uploaded file must be a CSV'}), 400
    
    # Get presentation title
    title = request.form.get('title', 'Flashcard Presentation')
    
    try:
        # Create presentation using service
        result = presentation_service.create_from_csv(credentials, csv_file, title)
        
        # Save presentation metadata to database
        presentation = Presentation.create_from_google_data(
            user_id=user_id,
            title=title,
            google_presentation_id=result['id'],
            google_url=result['url']
        )
        
        return jsonify({
            'message': 'Presentation created successfully',
            'presentation': presentation.to_dict()
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating presentation: {str(e)}", exc_info=True)
        return jsonify({'error': f'Failed to create presentation: {str(e)}'}), 500

@presentations_bp.route('/<int:presentation_id>', methods=['DELETE'])
def delete_presentation(presentation_id):
    """Delete presentation metadata (doesn't delete the actual Google Slides presentation)"""
    # Check if user is authenticated
    if 'credentials' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    # Get user info from credentials
    user_info = session.get('user_info', {})
    user_id = user_info.get('id')
    
    if not user_id:
        return jsonify({'error': 'User ID not found'}), 400
    
    # Query the presentation
    presentation = Presentation.query.filter_by(id=presentation_id, user_id=user_id).first()
    
    if not presentation:
        return jsonify({'error': 'Presentation not found'}), 404
    
    # Delete from database
    db.session.delete(presentation)
    db.session.commit()
    
    return jsonify({'message': 'Presentation deleted successfully'})