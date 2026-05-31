import os
from dotenv import load_dotenv

# Load env variables from a local .env file if it exists
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "foodrescue-secret-key")

    MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
    MYSQL_USER = os.environ.get("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "foodrescue")
    MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))