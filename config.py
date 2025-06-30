import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'nova-clip-secret-key-2025'
    
    # OpenAI Configuration
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY') or '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'
    
    # Google Custom Search Configuration
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY') or 'AIzaSyCXVNZjrHkmf65kFsMUThLe9_vGAe6ih7k'
    GOOGLE_CSE_ID = os.environ.get('GOOGLE_CSE_ID') or 'a71b1ebb654dc4e4b'
    
    # Session Configuration
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    
    # File Upload Configuration
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Output Directories
    TRENDS_OUTPUT_DIR = 'outputs/trends_data'
    SCRIPTS_OUTPUT_DIR = 'outputs/scripts'
    IMAGES_OUTPUT_DIR = 'outputs/images'
    
    # Processing Configuration
    MAX_NAMES_TO_SCRAPE = 25
    SCRAPING_TIMEOUT = 30
    SEARCH_RESULT_MIN = 1_000_000
    SEARCH_RESULT_MAX = 20_000_000
    IMAGES_PER_PERSON = 20

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}