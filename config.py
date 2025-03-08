import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'development-key'
    GOOGLE_CREDENTIALS_FILE = os.environ.get('GOOGLE_CREDENTIALS_FILE') or 'credentials.json'
    TOKEN_PICKLE_FILE = os.environ.get('TOKEN_PICKLE_FILE') or 'token.pickle'
    
    # Add more configuration options as needed

