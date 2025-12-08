# app_langscale/config/logging_config.py
import logging

LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[
            logging.FileHandler("language_detection_api.log"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("LanguageDetectionAPI")
