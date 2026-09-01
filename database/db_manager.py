from firebase.config import *
import json

def get_formatted_devices(db_name: Optional[str] = None, max_display: int = 70) -> list:
    """Get devices formatted with numbers"""
    devices = get_online_devices_from_db(db_name)
    targets = []
    idx = 1
    
    for device_id, data in devices.items():
        if idx > max_display:
            break
        targets.append({
            'number': idx,
            'id': device_id,
            'model': data.get('model', 'Unknown'),
            'sim': str(data.get('sim', 'N/A')),
            'from': data.get('from', 'Unknown'),
            'message': data.get('message', 'No message'),
            'time': data.get('time', 'Unknown')
        })
        idx += 1
    
    return targets

def get_all_formatted_devices(db_name: Optional[str] = None) -> list:
    """Get all devices formatted for admin"""
    devices = get_devices_from_db(db_name)
    targets = []
    idx = 1
    
    for device_id, data in devices.items():
        status = "🟢" if data.get('sim') and len(str(data.get('sim', '')).strip()) > 0 else "🔴"
        targets.append({
            'number': idx,
            'id': device_id,
            'model': data.get('model', 'Unknown'),
            'from': data.get('from', 'Unknown'),
            'time': data.get('time', 'Unknown'),
            'status': status,
            'sim': str(data.get('sim', 'N/A'))
        })
        idx += 1
    
    return targets
