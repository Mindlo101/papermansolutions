import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./papermansolutions.db")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    INTEREST_RATE = float(os.getenv("INTEREST_RATE", "30.0"))
    LATE_FEE_PERCENT = float(os.getenv("LATE_FEE_PERCENT", "5.0"))
    GRACE_PERIOD_DAYS = int(os.getenv("GRACE_PERIOD_DAYS", "3"))
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "app/static/uploads")
    
    # Company Details
    COMPANY_NAME = "Paperman Solutions (Pty) Ltd"
    COMPANY_ADDRESS = "2171 Section J, Botshabelo, 9781"
    COMPANY_PHONE = "068 472 4241"
    COMPANY_EMAIL = "ramanyakethabo@gmail.com"
    COMPANY_REG_NUMBER = "2026/XXXXXX/07"  # Update with your actual registration number

settings = Settings()