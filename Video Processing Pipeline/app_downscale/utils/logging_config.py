import logging
from config.settings import Settings

def setup_logging():
    """Configure logging for the application"""
    logging.basicConfig(
        level=getattr(logging, Settings.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(Settings.LOG_FILE),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)

logger = setup_logging()