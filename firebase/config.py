import firebase_admin
from firebase_admin import credentials, db
import os
import json
import base64
from typing import Dict, Optional

# Store all initialized Firebase apps
_firebase_apps = {}
_active_db_name = None

def init_firebase_database(db_name: str, db_url: str, cred_base64: str) -> firebase_admin.App:
    """Initialize a Firebase database instance"""
    try:
        if db_name in _firebase_apps:
            return _firebase_apps[db_name]
        
        cred_json = base64.b64decode(cred_base64).decode('utf-8')
        cred_dict = json.loads(cred_json)
        cred = credentials.Certificate(cred_dict)
        
        app = firebase_admin.initialize_app(cred, {
            'databaseURL': db_url
        }, name=db_name)
        
        _firebase_apps[db_name] = app
        return app
    except Exception as e:
        print(f"Failed to init {db_name}: {e}")
        return None

def get_active_database() -> str:
    """Get currently active database name"""
    global _active_db_name
    if not _active_db_name:
        _active_db_name = os.getenv('ACTIVE_DATABASE', 'myapp')
    return _active_db_name

def set_active_database(db_name: str):
    """Set active database (admin only)"""
    global _active_db_name
    _active_db_name = db_name
    return True

def get_all_databases() -> Dict[str, Dict]:
    """Get all configured Firebase databases"""
    databases = {}
    for key, value in os.environ.items():
        if key.startswith('FIREBASE_DB_') and key.endswith('_NAME'):
            index = key.replace('FIREBASE_DB_', '').replace('_NAME', '')
            name = value
            url_key = f'FIREBASE_DB_{index}_URL'
            cred_key = f'FIREBASE_DB_{index}_CRED'
            if url_key in os.environ and cred_key in os.environ:
                databases[name] = {
                    'url': os.environ[url_key],
                    'cred': os.environ[cred_key]
                }
    return databases

def get_devices_from_db(db_name: Optional[str] = None) -> Dict:
    """Get devices from specified database or active one"""
    if not db_name:
        db_name = get_active_database()
    
    databases = get_all_databases()
    if db_name not in databases:
        return {}
    
    app = init_firebase_database(db_name, databases[db_name]['url'], databases[db_name]['cred'])
    if not app:
        return {}
    
    ref = db.reference('devices', app=app)
    return ref.get() or {}

def get_device_by_id_from_db(device_id: str, db_name: Optional[str] = None) -> Optional[Dict]:
    """Get single device from specified database"""
    if not db_name:
        db_name = get_active_database()
    
    databases = get_all_databases()
    if db_name not in databases:
        return None
    
    app = init_firebase_database(db_name, databases[db_name]['url'], databases[db_name]['cred'])
    if not app:
        return None
    
    ref = db.reference(f'devices/{device_id}', app=app)
    return ref.get()

def add_device_to_db(device_id: str, device_data: Dict, db_name: Optional[str] = None) -> bool:
    """Add device to specified database"""
    if not db_name:
        db_name = get_active_database()
    
    databases = get_all_databases()
    if db_name not in databases:
        return False
    
    app = init_firebase_database(db_name, databases[db_name]['url'], databases[db_name]['cred'])
    if not app:
        return False
    
    ref = db.reference(f'devices/{device_id}', app=app)
    ref.set(device_data)
    return True

def delete_device_from_db(device_id: str, db_name: Optional[str] = None) -> bool:
    """Delete device from specified database"""
    if not db_name:
        db_name = get_active_database()
    
    databases = get_all_databases()
    if db_name not in databases:
        return False
    
    app = init_firebase_database(db_name, databases[db_name]['url'], databases[db_name]['cred'])
    if not app:
        return False
    
    ref = db.reference(f'devices/{device_id}', app=app)
    ref.delete()
    return True

def get_online_devices_from_db(db_name: Optional[str] = None) -> Dict:
    """Get only devices with SIM from specified database"""
    devices = get_devices_from_db(db_name)
    online = {}
    for device_id, data in devices.items():
        if data.get('sim') and len(str(data.get('sim', '')).strip()) > 0:
            online[device_id] = data
    return online

def get_offline_devices_from_db(db_name: Optional[str] = None) -> Dict:
    """Get devices without SIM from specified database"""
    devices = get_devices_from_db(db_name)
    offline = {}
    for device_id, data in devices.items():
        if not data.get('sim') or len(str(data.get('sim', '')).strip()) == 0:
            offline[device_id] = data
    return offline

def get_device_count_from_db(db_name: Optional[str] = None) -> Dict:
    """Get total, online, offline counts from specified database"""
    all_devices = get_devices_from_db(db_name)
    total = len(all_devices)
    online = 0
    offline = 0
    
    for data in all_devices.values():
        if data.get('sim') and len(str(data.get('sim', '')).strip()) > 0:
            online += 1
        else:
            offline += 1
    
    return {
        'total': total,
        'online': online,
        'offline': offline
    }
