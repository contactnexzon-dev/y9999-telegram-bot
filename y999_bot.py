<meta name='viewport' content='width=device-width, initial-scale=1'/>import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
import firebase_admin
from firebase_admin import credentials, firestore, auth
import datetime
import random
import string
import asyncio
from typing import Dict, Any

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
(PLAN_VERIFICATION, AWAITING_REFERRAL, MAIN_MENU, 
 WATCHING_AD, WITHDRAWAL_METHOD, WITHDRAWAL_ACCOUNT) = range(6)

# Constants
PLAN_PRICE = 2000
VERIFICATION_CODE = "ACTIVE2000"
JOINING_BONUS = 600
REFERRAL_REWARD = 500
AD_REWARD = 20
DAILY_AD_LIMIT = 5
MIN_WITHDRAWAL = 600
REQUIRED_REFERRALS = 3

# Get token from environment
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8592108961:AAHt-498WL8ZE9QrcTRNNBIwgN4WYQXOYLY')

# Initialize Firebase
firebase_config_json = os.environ.get('FIREBASE_CONFIG')
if firebase_config_json:
    firebase_config = json.loads(firebase_config_json)
    cred = credentials.Certificate(firebase_config)
else:
    cred = credentials.Certificate('serviceAccountKey.json')

firebase_admin.initialize_app(cred)
db = firestore.client()

class Y999Bot:
    def __init__(self):
        self.user_sessions = {}
        self.application = None
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler"""
        user = update.effective_user
        context.user_data['telegram_id'] = user.id
        
        # Check if user exists in Firebase
        users_ref = db.collection('users')
        query = users_ref.where('telegram_id', '==', str(user.id)).limit(1)
        existing_users = query.get()
        
        if existing_users:
            # User exists, show main menu
            user_doc = existing_users[0]
            context.user_data['firebase_uid'] = user_doc.id
            await self.show_main_menu(update, context)
        else:
            # New user, show plan purchase
            await self.show_plan_purchase(update, context)
        
        return PLAN_VERIFICATION
    
    async def show_plan_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show plan purchase information"""
        message = (
            "🌟 *Welcome to Y999 - Pakistan's Premier Rewards Platform!* 🌟\n\n"
            "To get started, you need to activate your account with our Starter Plan:\n\n"
            "💰 *Plan Details:*\n"
            "• Price: PKR 2,000 (One-time payment)\n"
            "• Joining Bonus: 600 PKR (Locked until 3 referrals)\n"
            "• Daily Earnings: 100 PKR (5 ads × 20 PKR)\n"
            "• Per Referral: 500 PKR\n\n"
            "📱 *Payment Instructions:*\n"
            "1. Open Easypaisa app\n"
            "2. Send PKR 2,000 to:\n"
            "   • Account: M. Azan\n"
            "   • Number: 03284009737\n"
            "3. After payment, type the verification code below\n\n"
            "🔑 *Verification Code:* `ACTIVE2000`\n\n"
            "Type the verification code to continue..."
        )
        
        await update.message.reply_text(
            message,
            parse_mode='Markdown'
        )
    
    async def verify_plan(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Verify plan activation code"""
        user_code = update.message.text.strip().upper()
        
        if user_code == VERIFICATION_CODE:
            context.user_data['plan_verified'] = True
            await update.message.reply_text(
                "✅ *Payment Verified!*\n\n"
                "Now let's create your account. Please enter your full name:",
                parse_mode='Markdown'
            )
            return AWAITING_REFERRAL
        else:
            await update.message.reply_text(
                "❌ *Invalid verification code*\n\n"
                "Please check your payment and try again.\n"
                "Verification code: `ACTIVE2000`",
                parse_mode='Markdown'
            )
            return PLAN_VERIFICATION
    
    async def get_user_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get user's name and ask for referral code"""
        context.user_data['user_name'] = update.message.text
        
        await update.message.reply_text(
            f"Nice to meet you, {context.user_data['user_name']}!\n\n"
            "Do you have a referral code? If yes, enter it now.\n"
            "If not, just type 'skip' to continue without referral:"
        )
        return self.process_referral
    
    async def process_referral(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process referral code and create user account"""
        referral_input = update.message.text.strip()
        referred_by = None
        
        if referral_input.lower() != 'skip':
            # Check if referral code exists
            users_ref = db.collection('users')
            query = users_ref.where('referralCode', '==', referral_input).limit(1)
            referrer_docs = query.get()
            
            if referrer_docs:
                referred_by = referrer_docs[0].id
        
        # Create user in Firebase Auth
        try:
            # Generate email from telegram ID
            email = f"user_{context.user_data['telegram_id']}@y999.com"
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            
            # Create Firebase Auth user
            user = auth.create_user(
                email=email,
                password=password,
                display_name=context.user_data['user_name']
            )
            
            # Generate unique referral code
            referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            
            # Create user document in Firestore
            user_data = {
                'uid': user.uid,
                'name': context.user_data['user_name'],
                'email': email,
                'telegram_id': str(context.user_data['telegram_id']),
                'balance': JOINING_BONUS,
                'referralCode': referral_code,
                'referredBy': referred_by,
                'dailyAdCount': 0,
                'dailyEarnings': 0,
                'lastAdWatchDate': datetime.datetime.now().isoformat(),
                'totalAdsWatched': 0,
                'totalEarnings': JOINING_BONUS,
                'successfulWithdrawals': 0,
                'referralsCount': 0,
                'referralEarnings': 0,
                'totalReferrals': 0,
                'challengeCompleted': False,
                'joiningBonusLocked': True,
                'planActivated': True,
                'planPrice': PLAN_PRICE,
                'planActivatedAt': firestore.SERVER_TIMESTAMP,
                'createdAt': firestore.SERVER_TIMESTAMP,
                'isBlocked': False
            }
            
            db.collection('users').document(user.uid).set(user_data)
            
            # Update referrer if exists
            if referred_by:
                referrer_ref = db.collection('users').document(referred_by)
                referrer = referrer_ref.get()
                if referrer.exists:
                    referrer_data = referrer.to_dict()
                    
                    # Update referrer's stats
                    referrer_ref.update({
                        'balance': firestore.Increment(REFERRAL_REWARD),
                        'referralsCount': firestore.Increment(1),
                        'totalReferrals': firestore.Increment(1),
                        'referralEarnings': firestore.Increment(REFERRAL_REWARD)
                    })
                    
                    # Check if referrer completes challenge
                    if referrer_data.get('referralsCount', 0) + 1 >= REQUIRED_REFERRALS:
                        referrer_ref.update({
                            'challengeCompleted': True,
                            'joiningBonusLocked': False
                        })
                    
                    # Create notification for referrer
                    notification_data = {
                        'userId': referred_by,
                        'title': '🎉 New Referral!',
                        'message': f'{context.user_data["user_name"]} joined using your referral code! You earned 500 PKR!',
                        'createdAt': firestore.SERVER_TIMESTAMP,
                        'read': False
                    }
                    db.collection('notifications').add(notification_data)
            
            context.user_data['firebase_uid'] = user.uid
            context.user_data['login_credentials'] = {
                'email': email,
                'password': password
            }
            
            # Send login credentials
            await update.message.reply_text(
                "✅ *Account Created Successfully!*\n\n"
                f"*Your Login Credentials:*\n"
                f"Email: `{email}`\n"
                f"Password: `{password}`\n\n"
                "⚠️ *Save these credentials!*\n"
                "You'll need them to log in to the web app.\n\n"
                "Now let's explore Y999!",
                parse_mode='Markdown'
            )
            
            await self.show_main_menu(update, context)
            return MAIN_MENU
            
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            await update.message.reply_text(
                "❌ An error occurred while creating your account. Please try again later."
            )
            return ConversationHandler.END
    
    async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show main menu with inline buttons"""
        uid = context.user_data.get('firebase_uid')
        if not uid:
            return
        
        user_doc = db.collection('users').document(uid).get()
        if not user_doc.exists:
            return
        
        user_data = user_doc.to_dict()
        
        # Calculate available balance
        available_balance = user_data['balance']
        locked_amount = JOINING_BONUS if user_data['joiningBonusLocked'] else 0
        withdrawable = available_balance - locked_amount
        
        # Check daily reset
        today = datetime.datetime.now().date().isoformat()
        if user_data.get('lastAdWatchDate', '').split('T')[0] != today:
            user_data['dailyAdCount'] = 0
            user_data['dailyEarnings'] = 0
            db.collection('users').document(uid).update({
                'dailyAdCount': 0,
                'dailyEarnings': 0,
                'lastAdWatchDate': datetime.datetime.now().isoformat()
            })
        
        message = (
            f"🏠 *Y999 Dashboard*\n\n"
            f"👤 *User:* {user_data['name']}\n"
            f"💰 *Total Balance:* {user_data['balance']} PKR\n"
            f"🔒 *Locked Bonus:* {locked_amount} PKR\n"
            f"💵 *Withdrawable:* {withdrawable} PKR\n\n"
            f"📊 *Today's Progress:*\n"
            f"• Ads watched: {user_data['dailyAdCount']}/{DAILY_AD_LIMIT}\n"
            f"• Today's earnings: {user_data['dailyEarnings']} PKR\n"
            f"• Referrals: {user_data['referralsCount']}/{REQUIRED_REFERRALS}\n\n"
            f"🎯 *Challenge Progress:*\n"
        )
        
        # Progress bar
        progress = min(100, (user_data['referralsCount'] / REQUIRED_REFERRALS) * 100)
        filled = int(progress / 10)
        message += f"`{'█' * filled}{'░' * (10 - filled)}` {progress:.0f}%\n"
        
        if user_data['joiningBonusLocked']:
            message += "⚠️ Complete 3 referrals to unlock your 600 PKR bonus!"
        else:
            message += "✅ Challenge Complete! Bonus Unlocked! 🎉"
        
        keyboard = [
            [InlineKeyboardButton("📺 Watch Ads", callback_data='watch_ads')],
            [InlineKeyboardButton("👥 Refer & Earn", callback_data='refer')],
            [InlineKeyboardButton("💳 Withdraw", callback_data='withdraw')],
            [InlineKeyboardButton("📊 Profile", callback_data='profile')],
            [InlineKeyboardButton("🔔 Notifications", callback_data='notifications')]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.message:
            await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
        else:
            await update.callback_query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks"""
        query = update.callback_query
        await query.answer()
        
        action = query.data
        
        if action == 'watch_ads':
            await self.watch_ad(update, context)
        elif action == 'refer':
            await self.show_referral(update, context)
        elif action == 'withdraw':
            await self.start_withdrawal(update, context)
        elif action == 'profile':
            await self.show_profile(update, context)
        elif action == 'notifications':
            await self.show_notifications(update, context)
        elif action == 'back_to_menu':
            await self.show_main_menu(update, context)
        elif action.startswith('withdraw_'):
            method = action.replace('withdraw_', '')
            context.user_data['withdrawal_method'] = method
            await query.edit_message_text(
                f"Please enter your {method} account number (03XXXXXXXXX):"
            )
            return WITHDRAWAL_ACCOUNT
        elif action == 'watch_ad_confirm':
            await self.process_ad_watch(update, context)
    
    async def watch_ad(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show ad watching interface"""
        query = update.callback_query
        uid = context.user_data.get('firebase_uid')
        
        user_doc = db.collection('users').document(uid).get()
        user_data = user_doc.to_dict()
        
        if user_data['dailyAdCount'] >= DAILY_AD_LIMIT:
            await query.edit_message_text(
                "⚠️ *Daily limit reached!*\n\n"
                f"You've watched all {DAILY_AD_LIMIT} ads for today.\n"
                "Come back tomorrow for more earnings!",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Back to Menu", callback_data='back_to_menu')
                ]])
            )
            return
        
        remaining = DAILY_AD_LIMIT - user_data['dailyAdCount']
        message = (
            "📺 *Watch Ad*\n\n"
            f"Today's progress: {user_data['dailyAdCount']}/{DAILY_AD_LIMIT}\n"
            f"Remaining ads: {remaining}\n"
            f"Reward per ad: {AD_REWARD} PKR\n\n"
            "Click the button below to watch an ad and earn!"
        )
        
        keyboard = [
            [InlineKeyboardButton("▶️ Watch Ad (20 PKR)", callback_data='watch_ad_confirm')],
            [InlineKeyboardButton("◀️ Back to Menu", callback_data='back_to_menu')]
        ]
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def process_ad_watch(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process ad watch and reward user"""
        query = update.callback_query
        uid = context.user_data.get('firebase_uid')
        
        user_ref = db.collection('users').document(uid)
        user_doc = user_ref.get()
        user_data = user_doc.to_dict()
        
        if user_data['dailyAdCount'] >= DAILY_AD_LIMIT:
            await query.edit_message_text(
                "❌ Daily limit reached!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Back to Menu", callback_data='back_to_menu')
                ]])
            )
            return
        
        # Update user balance and stats
        new_balance = user_data['balance'] + AD_REWARD
        new_daily_count = user_data['dailyAdCount'] + 1
        new_daily_earnings = user_data['dailyEarnings'] + AD_REWARD
        
        user_ref.update({
            'balance': new_balance,
            'dailyAdCount': new_daily_count,
            'dailyEarnings': new_daily_earnings,
            'totalAdsWatched': firestore.Increment(1),
            'totalEarnings': firestore.Increment(AD_REWARD)
        })
        
        await query.edit_message_text(
            f"✅ *Ad Watched Successfully!*\n\n"
            f"💰 You earned: {AD_REWARD} PKR\n"
            f"📊 Today's total: {new_daily_earnings} PKR\n"
            f"⏱️ Remaining ads: {DAILY_AD_LIMIT - new_daily_count}\n\n"
            f"Your new balance: {new_balance} PKR",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📺 Watch Another Ad", callback_data='watch_ads')],
                [InlineKeyboardButton("◀️ Back to Menu", callback_data='back_to_menu')]
            ])
        )
    
    async def show_referral(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show referral information"""
        query = update.callback_query
        uid = context.user_data.get('firebase_uid')
        
        user_doc = db.collection('users').document(uid).get()
        user_data = user_doc.to_dict()
        
        message = (
            "👥 *Refer & Earn*\n\n"
            f"*Your Referral Code:* `{user_data['referralCode']}`\n\n"
            "🎁 *Rewards:*\n"
            "• 500 PKR per referral\n"
            "• Bonus 600 PKR unlocked after 3 referrals\n\n"
            f"📊 *Your Progress:*\n"
            f"• Referrals: {user_data['referralsCount']}/{REQUIRED_REFERRALS}\n"
            f"• Earnings from referrals: {user_data['referralEarnings']} PKR\n\n"
            "📱 *How to refer:*\n"
            "1. Share your referral code with friends\n"
            "2. They enter it during registration\n"
            "3. You get 500 PKR instantly!\n\n"
            "👇 *Share your code:*"
        )
        
        # Progress bar
        progress = min(100, (user_data['referralsCount'] / REQUIRED_REFERRALS) * 100)
        filled = int(progress / 10)
        message += f"\n`{'█' * filled}{'░' * (10 - filled)}` {progress:.0f}%"
        
        keyboard = [
            [InlineKeyboardButton("📤 Share Code", switch_inline_query=f"Join Y999 with my referral code: {user_data['referralCode']}")],
            [InlineKeyboardButton("◀️ Back to Menu", callback_data='back_to_menu')]
        ]
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def start_withdrawal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start withdrawal process"""
        query = update.callback_query
        uid = context.user_data.get('firebase_uid')
        
        user_doc = db.collection('users').document(uid).get()
        user_data = user_doc.to_dict()
        
        # Calculate available balance
        available = user_data['balance']
        if user_data['joiningBonusLocked']:
            available -= JOINING_BONUS
        
        if available < MIN_WITHDRAWAL:
            await query.edit_message_text(
                f"❌ *Insufficient Balance*\n\n"
                f"Minimum withdrawal: {MIN_WITHDRAWAL} PKR\n"
                f"Your available balance: {available} PKR\n\n"
               f"Keep earning to reach the minimum!",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("◀️ Back to Menu", callback_data='back_to_menu')
                ]])
            )
            return
        
        message = (
            "💳 *Withdraw Earnings*\n\n"
            f"Your available balance: {available} PKR\n"
            f"Minimum withdrawal: {MIN_WITHDRAWAL} PKR\n\n"
            "Select payment method:"
        )
        
        keyboard = [
            [InlineKeyboardButton("📱 JazzCash", callback_data='withdraw_jazzcash')],
            [InlineKeyboardButton("📱 Easypaisa", callback_data='withdraw_easypaisa')],
            [InlineKeyboardButton("◀️ Back to Menu", callback_data='back_to_menu')]
        ]
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def process_withdrawal_account(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process withdrawal account number"""
        account_number = update.message.text.strip()
        method = context.user_data.get('withdrawal_method')
        uid = context.user_data.get('firebase_uid')
        
        # Validate account number
        if not account_number.startswith('03') or len(account_number) != 11 or not account_number.isdigit():
            await update.message.reply_text(
                "❌ *Invalid account number*\n\n"
                "Please enter a valid 11-digit number starting with 03 (e.g., 03123456789):",
                parse_mode='Markdown'
            )
            return WITHDRAWAL_ACCOUNT
        
        user_doc = db.collection('users').document(uid).get()
        user_data = user_doc.to_dict()
        
        # Calculate available balance
        available = user_data['balance']
        if user_data['joiningBonusLocked']:
            available -= JOINING_BONUS
        
        # Create withdrawal request
        withdrawal_data = {
            'userId': uid,
            'userName': user_data['name'],
            'userEmail': user_data['email'],
            'amount': available,
            'pkrAmount': available,
            'method': method.capitalize(),
            'accountDetails': account_number,
            'status': 'pending',
            'requestedAt': firestore.SERVER_TIMESTAMP
        }
        
        db.collection('withdrawals').add(withdrawal_data)
        
        await update.message.reply_text(
            f"✅ *Withdrawal Request Submitted!*\n\n"
            f"Amount: {available} PKR\n"
            f"Method: {method.capitalize()}\n"
            f"Account: {account_number}\n\n"
            f"⏱️ Processing time: 24-48 hours\n"
            f"You'll be notified once processed.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Back to Menu", callback_data='back_to_menu')
            ]])
        )
        
        return MAIN_MENU
    
    async def show_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user profile"""
        query = update.callback_query
        uid = context.user_data.get('firebase_uid')
        
        user_doc = db.collection('users').document(uid).get()
        user_data = user_doc.to_dict()
        
        # Get withdrawal history
        withdrawals_ref = db.collection('withdrawals').where('userId', '==', uid).order_by('requestedAt', direction='DESCENDING').limit(5)
        withdrawals = withdrawals_ref.get()
        
        message = (
            f"👤 *Profile Information*\n\n"
            f"*Name:* {user_data['name']}\n"
            f"*Email:* {user_data['email']}\n"
            f"*Referral Code:* `{user_data['referralCode']}`\n"
            f"*Member since:* {user_data['createdAt'].strftime('%Y-%m-%d') if user_data.get('createdAt') else 'Today'}\n\n"
            f"📊 *Statistics*\n"
            f"• Total Earnings: {user_data['totalEarnings']} PKR\n"
            f"• Total Ads: {user_data['totalAdsWatched']}\n"
            f"• Total Referrals: {user_data['totalReferrals']}\n"
            f"• Successful Withdrawals: {user_data['successfulWithdrawals']}\n\n"
        )
        
        if withdrawals:
            message += "📝 *Recent Withdrawals:*\n"
            for w in withdrawals:
                w_data = w.to_dict()
                status_icon = "✅" if w_data['status'] == 'completed' else "⏳" if w_data['status'] == 'pending' else "❌"
                message += f"{status_icon} {w_data['pkrAmount']} PKR - {w_data['status']}\n"
        
        keyboard = [[InlineKeyboardButton("◀️ Back to Menu", callback_data='back_to_menu')]]
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def show_notifications(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user notifications"""
        query = update.callback_query
        uid = context.user_data.get('firebase_uid')
        
        # Get user notifications
        notifications_ref = db.collection('notifications').where('userId', '==', uid).order_by('createdAt', direction='DESCENDING').limit(10)
        notifications = notifications_ref.get()
        
        if not notifications:
            message = "🔔 *No Notifications*\n\nYou don't have any notifications yet."
        else:
            message = "🔔 *Recent Notifications*\n\n"
            for notif in notifications:
                notif_data = notif.to_dict()
                time_str = notif_data['createdAt'].strftime('%Y-%m-%d %H:%M') if notif_data.get('createdAt') else 'Recent'
                message += f"*{notif_data['title']}*\n{notif_data['message']}\n`{time_str}`\n\n"
                
                # Mark as read
                notif.reference.update({'read': True})
        
        keyboard = [[InlineKeyboardButton("◀️ Back to Menu", callback_data='back_to_menu')]]
        
        await query.edit_message_text(
            message,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command handler"""
        help_text = (
            "🤖 *Y999 Bot Commands*\n\n"
            "/start - Start the bot and access main menu\n"
            "/help - Show this help message\n"
            "/balance - Check your current balance\n"
            "/referral - Get your referral code\n"
            "/withdraw - Request a withdrawal\n"
            "/stats - View your statistics\n\n"
            "Need more help? Contact @Y999Support"
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check balance command"""
        uid = context.user_data.get('firebase_uid')
        if not uid:
            await update.message.reply_text("Please use /start first to login.")
            return
        
        user_doc = db.collection('users').document(uid).get()
        user_data = user_doc.to_dict()
        
        locked = JOINING_BONUS if user_data['joiningBonusLocked'] else 0
        message = (
            f"💰 *Your Balance*\n\n"
            f"Total: {user_data['balance']} PKR\n"
            f"Locked: {locked} PKR\n"
            f"Available: {user_data['balance'] - locked} PKR"
        )
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Update {update} caused error {context.error}")
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "An error occurred. Please try again later."
                )
        except:
            pass