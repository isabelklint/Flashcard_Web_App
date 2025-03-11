# app.py - Updated version
from flask import Flask, render_template, session
from api.routes.presentations import presentations_bp
from api.routes.auth import auth_bp
from models.presentation import db
import os
import logging

# Add these lines at the top of app.py, after the imports
import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # Allow OAuth without HTTPS for development

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create app
app = Flask(__name__, 
            static_folder='web/static',
            template_folder='web/templates')

# Configure the app
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['SESSION_TYPE'] = 'filesystem'

# Configure database
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URI', 'sqlite:///flashcards.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

# Ensure database tables are created
with app.app_context():
    db.create_all()

# Register blueprints
app.register_blueprint(presentations_bp)
app.register_blueprint(auth_bp)

@app.route('/')
def home():
    """Render the home page"""
    return render_template('dashboard/index.html')

@app.route('/pricing')
def pricing():
    """Render the pricing page"""
    return render_template('dashboard/pricing.html')

@app.route('/documentation')
def documentation():
    """Render the documentation page"""
    return render_template('dashboard/documentation.html')

if __name__ == '__main__':
    app.run(debug=True, port=5001, host='localhost')