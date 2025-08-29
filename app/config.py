import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))



# Load environment variables
load_dotenv(os.path.join(basedir, '..', '.env'))

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY') or 'default-secret-key'
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URI') or 'sqlite:///' + os.path.join(basedir, 'site.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
    GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY') or 'your-google-maps-api-key'