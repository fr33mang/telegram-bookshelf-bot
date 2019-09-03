import os

# telegram bot config
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
PORT = int(os.environ.get("PORT", "8443"))
APP_URL = os.environ.get("APP_URL", "")

# goodreads api keys
CONSUMER_KEY = os.environ.get('CONSUMER_KEY', '')
CONSUMER_SECRET = os.environ.get('CONSUMER_SECRET', '')
