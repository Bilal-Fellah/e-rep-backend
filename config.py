import os

SECRET_KEY = os.environ.get("SECRET_KEY", "dev_key")
DEBUG = True
SCHEDULER_API_ENABLED = True
