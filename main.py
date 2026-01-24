import logging
import sys
from smart_extractor import SmartExtractor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout
)

if __name__ == "__main__":
    extractor = SmartExtractor(config_path='config.json')
    extractor.extract_all()
