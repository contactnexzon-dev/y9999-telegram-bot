<meta name='viewport' content='width=device-width, initial-scale=1'/>import logging
import os
import json
import threading
import time
from flask import Flask, request
from y999_bot import Y999Bot, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler, Update
from telegram.ext import Application

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Flask
app = Flask(__name__)

# Bot token
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8592108961:AAHt-498WL8ZE9QrcTRNNBIwgN4WYQXOYLY')

# Initialize bot
bot_instance = Y999Bot()
application = Application.builder().token(BOT_TOKEN).build()

# Define conversation states (same as in bot)
PLAN_VERIFICATION, AWAITING_REFERRAL, MAIN_MENU, WITHDRAWAL_ACCOUNT = range(4)

# Add handlers
conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', bot_instance.start)],
    states={
        PLAN_VERIFICATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_instance.verify_plan)],
        AWAITING_REFERRAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_instance.get_user_name)],
        MAIN_MENU: [CallbackQueryHandler(bot_instance.handle_callback)],
        WITHDRAWAL_ACCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot_instance.process_withdrawal_account)]
    },
    fallbacks=[CommandHandler('start', bot_instance.start)]
)

application.add_handler(conv_handler)
application.add_handler(CommandHandler('help', bot_instance.help_command))
application.add_handler(CommandHandler('balance', bot_instance.balance_command))
application.add_error_handler(bot_instance.error_handler)

bot_instance.application = application

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle Telegram webhook"""
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        application.process_update(update)
        return 'OK', 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'Error', 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return 'OK', 200

@app.route('/')
def index():
    """Root endpoint"""
    return 'Y999 Bot is running!', 200

def run_polling():
    """Run bot in polling mode as backup"""
    time.sleep(10)  # Wait for Flask to start
    try:
        logger.info("Starting bot in polling mode...")
        application.run_polling()
    except Exception as e:
        logger.error(f"Polling error: {e}")

if __name__ == '__main__':
    # Start polling in background thread
    polling_thread = threading.Thread(target=run_polling, daemon=True)
    polling_thread.start()
    
    # Run Flask app
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)