import logging
import os
import json
import threading
import time
from flask import Flask, request

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Flask
app = Flask(__name__)

@app.route('/')
def index():
    return 'Y999 Bot is running!', 200

@app.route('/health')
def health():
    return 'OK', 200

@app.route('/webhook', methods=['POST'])
def webhook():
    return 'OK', 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
