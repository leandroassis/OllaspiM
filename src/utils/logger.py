import logging
import sys
import os

def setup_logger(name: str = "LaspiLM") -> logging.Logger:
    """Configures and returns the central logger."""
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        
        # Formatters
        console_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s", 
            datefmt="%H:%M:%S"
        )
        file_formatter = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
        )
        
        # Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # File Handler
        os.makedirs("logs", exist_ok=True)
        file_handler = logging.FileHandler("logs/app.log", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
    return logger

logger = setup_logger()
