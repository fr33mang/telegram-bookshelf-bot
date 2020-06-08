import os

# Telegram bot config
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
PORT = int(os.environ.get("PORT", "8443"))
APP_URL = os.environ.get("APP_URL", "")

# Postgres connection string
DATABASE_URL = os.environ.get('DATABASE_URL',
                              'postgresql://postgres:postgres@postgres:5432/')

# Goodreads api keys
CONSUMER_KEY = os.environ.get('CONSUMER_KEY', '')
CONSUMER_SECRET = os.environ.get('CONSUMER_SECRET', '')
