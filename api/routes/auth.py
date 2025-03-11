# api/routes/auth.py - Updated version
from flask import Blueprint, request, redirect, url_for, session, jsonify
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import json
import os

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# This path should be where you store your OAuth client secrets file
GOOGLE_CLIENT_SECRETS_FILE = os.environ.get('GOOGLE_CLIENT_SECRETS_FILE', 'credentials.json')

# OAuth scopes needed for the application
SCOPES = ['https://www.googleapis.com/auth/presentations', 
          'https://www.googleapis.com/auth/drive',
          'https://www.googleapis.com/auth/userinfo.profile']

@auth_bp.route('/login')
def login():
    """Initiate the OAuth flow for Google authentication"""
    # Create flow instance with client secrets file
    flow = Flow.from_client_secrets_file(
        GOOGLE_CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=url_for('auth.oauth2callback', _external=True)
    )
    
    # Generate authorization URL
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'  # Force consent to ensure refresh token
    )
    
    # Store the state so the callback can verify the auth server response
    session['state'] = state
    
    # Redirect user to Google's OAuth page
    return redirect(authorization_url)

@auth_bp.route('/oauth2callback')
def oauth2callback():
    """Handle the OAuth callback from Google"""
    # Verify state matches to prevent CSRF attacks
    state = session['state']
    
    flow = Flow.from_client_secrets_file(
        GOOGLE_CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        state=state,
        redirect_uri=url_for('auth.oauth2callback', _external=True)
    )
    
    # Use the authorization server's response to fetch the tokens
    authorization_response = request.url
    flow.fetch_token(authorization_response=authorization_response)
    
    # Get credentials from flow
    credentials = flow.credentials
    
    # Save credentials in session
    session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    
    # Get user info
    try:
        user_info_service = build('oauth2', 'v2', credentials=credentials)
        user_info = user_info_service.userinfo().get().execute()
        session['user_info'] = user_info
    except Exception as e:
        print(f"Error getting user info: {e}")
        # Continue even if we couldn't get user info
    
    # Redirect to the main application page
    return redirect(url_for('home'))

@auth_bp.route('/logout')
def logout():
    """Log out the user and clear session"""
    session.clear()
    return redirect(url_for('home'))

@auth_bp.route('/status')
def status():
    """Check if user is authenticated and return user info"""
    if 'credentials' in session:
        return jsonify({
            'authenticated': True,
            'user_info': session.get('user_info', {})
        })
    return jsonify({'authenticated': False})