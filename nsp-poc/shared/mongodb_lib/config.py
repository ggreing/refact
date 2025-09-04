import os
import logging
from zoneinfo import ZoneInfo
from datetime import datetime
from dotenv import load_dotenv


KST = ZoneInfo("Asia/Seoul")


class MongoConfig:
    def __init__(self, mongo_uri: str = None, log_level: int = logging.INFO):
        load_dotenv()
        self.mongo_uri = mongo_uri or os.getenv('MONGO_URI')
        self.log_level = log_level
        self.kst = KST
        
        if not self.mongo_uri:
            raise ValueError("MONGO_URI must be provided either as parameter or environment variable")
        
        self._setup_logging()
    
    def _setup_logging(self):
        os.makedirs('log', exist_ok=True)
        logging.basicConfig(
            level=self.log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filename='log/mongo_log.log',
            filemode='a'
        )
    
    @property
    def current_time(self) -> datetime:
        return datetime.now(self.kst)