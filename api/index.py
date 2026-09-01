import os
import logging
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import firebase_admin
from firebase_admin import credentials, db
import base64
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = set(x.strip() for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip())
FIREBASE_DB_URL = os.getenv("FIREBASE_DB_URL")
FIREBASE_CRED_BASE64 = os.getenv("FIREBASE_CRED_BASE64")

# ============ FASTAPI APP (must exist at import time, top-level) ============
app = FastAPI()

# ============ LAZY GLOBALS ============
# These are only built on first use, NOT at import time.
# This is what fixes the "does not export app" Vercel error: if BOT_TOKEN or
# Firebase creds are missing/misconfigured, we fail loudly on the first
# request instead of crashing the whole module import.
_telegram_app = None
_firebase_app = None


def get_firebase():
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app
    if not FIREBASE_DB_URL or not FIREBASE_CRED_BASE64:
        raise RuntimeError("FIREBASE_DB_URL / FIREBASE_CRED_BASE64 not set")
    cred_json = base64.b64decode(FIREBASE_CRED_BASE64).decode("utf-8")
    cred_dict = json.loads(cred_json)
    cred = credentials.Certificate(cred_dict)
    _firebase_app = firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})
    return _firebase_app


# ============ DEVICE DATA HELPERS ============
def get_devices():
    fb = get_firebase()
    ref = db.reference("devices", app=fb)
    return ref.get() or {}


def get_device(device_id):
    fb = get_firebase()
    ref = db.reference(f"devices/{device_id}", app=fb)
    return ref.get()


def update_device_field(device_id, field, value):
    fb = get_firebase()
    ref = db.reference(f"devices/{device_id}/{field}", app=fb)
    ref.set(value)


def request_ping(device_id):
    """Sets a flag the Android agent polls for to force an immediate status push."""
    fb = get_firebase()
    ref = db.reference(f"devices/{device_id}/ping_requested", app=fb)
    ref.set(True)


def request_location(device_id):
    """Sets a flag the Android agent polls for to fetch + report current location."""
    fb = get_firebase()
    ref = db.reference(f"devices/{device_id}/location_requested", app=fb)
    ref.set(True)


def is_admin(user_id):
    return str(user_id) in ADMIN_IDS


def fmt_last_seen(iso_str):
    if not iso_str:
        return "never"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - dt
        mins = int(delta.total_seconds() // 60)
        if mins < 60:
            return f"{mins}m ago"
        hours = mins // 60
        if hours < 24:
            return f"{hours}h ago"
        return f"{hours // 24}d ago"
    except Exception:
        return iso_str


# ============ BOT COMMANDS ============
async def cmd_devices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    devices = get_devices()
    if not devices:
        await update.message.reply_text("📭 No devices registered.")
        return
    lines = ["📱 *Your Devices*\n"]
    for did, data in devices.items():
        name = data.get("name", did)
        battery = data.get("battery", "?")
        seen = fmt_last_seen(data.get("last_seen"))
        online = "🟢" if seen != "never" and "m ago" in seen and int(seen.split("m")[0]) < 30 else "⚪"
        lines.append(f"{online} *{name}* (`{did}`) — 🔋{battery}% — {seen}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /status <device_id>")
        return
    did = context.args[0]
    data = get_device(did)
    if not data:
        await update.message.reply_text(f"❌ Device `{did}` not found.", parse_mode="Markdown")
        return
    name = data.get("name", did)
    battery = data.get("battery", "?")
    storage = data.get("storage_free_gb", "?")
    seen = fmt_last_seen(data.get("last_seen"))
    await update.message.reply_text(
        f"📊 *{name}*\n\n🔋 Battery: {battery}%\n💾 Free storage: {storage} GB\n🕐 Last seen: {seen}",
        parse_mode="Markdown",
    )


async def cmd_locate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /locate <device_id>")
        return
    did = context.args[0]
    data = get_device(did)
    if not data:
        await update.message.reply_text(f"❌ Device `{did}` not found.", parse_mode="Markdown")
        return
    request_location(did)
    await update.message.reply_text(
        f"📍 Location request sent to `{did}`.\nAgent will report back on its next poll — "
        f"then run /locate {did} again to see the fresh coordinates.",
        parse_mode="Markdown",
    )
    loc = data.get("location")
    if loc:
        await update.message.reply_text(
            f"Last known: {loc.get('lat')}, {loc.get('lng')} at {loc.get('timestamp')}"
        )


async def cmd_apps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /apps <device_id>")
        return
    did = context.args[0]
    data = get_device(did)
    if not data:
        await update.message.reply_text(f"❌ Device `{did}` not found.", parse_mode="Markdown")
        return
    apps = data.get("installed_apps", [])
    if not apps:
        await update.message.reply_text("No app list reported yet.")
        return
    msg = f"📦 *Installed apps on {data.get('name', did)}*\n\n" + "\n".join(f"• {a}" for a in apps[:100])
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Unauthorized.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /ping <device_id>")
        return
    did = context.args[0]
    data = get_device(did)
    if not data:
        await update.message.reply_text(f"❌ Device `{did}` not found.", parse_mode="Markdown")
        return
    request_ping(did)
    await update.message.reply_text(f"📡 Ping sent to `{did}`. It'll push a fresh status on its next check.", parse_mode="Markdown")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Device Fleet Manager Bot\n\n"
        "/devices — list all devices\n"
        "/status <id> — battery, storage, last seen\n"
        "/locate <id> — request current location\n"
        "/apps <id> — installed apps\n"
        "/ping <id> — force a status update"
    )


# ============ LAZY TELEGRAM APP BUILD ============
def get_telegram_app():
    global _telegram_app
    if _telegram_app is not None:
        return _telegram_app
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN env var is not set")
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("devices", cmd_devices))
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("locate", cmd_locate))
    application.add_handler(CommandHandler("apps", cmd_apps))
    application.add_handler(CommandHandler("ping", cmd_ping))
    _telegram_app = application
    return _telegram_app


# ============ WEBHOOK ENDPOINT ============
@app.post("/api/index")
@app.post("/api/index/{path:path}")
async def handle_webhook(request: Request):
    try:
        telegram_app = get_telegram_app()
        body = await request.json()
        async with telegram_app:
            update = Update.de_json(body, telegram_app.bot)
            await telegram_app.process_update(update)
        return Response(status_code=200)
    except Exception as e:
        logger.exception(f"Webhook error: {e}")
        # Still return 200 so Telegram doesn't retry-storm you, but log the real cause.
        return Response(status_code=200)


@app.get("/api/index")
async def health():
    return {"status": "ok"}


# ============ LOCAL TESTING ============
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
