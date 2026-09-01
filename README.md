# OTPx Bot

Telegram bot for OTP sniffing with multi-Firebase support.

## Setup

1. Clone repo
2. Install dependencies: `pip install -r requirements.txt`
3. Add Firebase credentials (base64 encoded)
4. Set environment variables in Vercel
5. Deploy

## Commands

### User
- `/start` - Show targets
- `/help` - Help

### Admin
- `/admin` - Admin panel
- `/databases` - List databases
- `/switch <name>` - Switch DB
- `/add` - Add device
- `/list` - List all
- `/online` - Online only
- `/offline` - Offline only
- `/toggle <id> <sim>` - Toggle status
- `/delete <id>` - Delete device
- `/stats` - Statistics
