import os
from dotenv import load_dotenv

load_dotenv()

botToken = os.environ.get("BOT_TOKEN", "")
ownerId = int(os.environ.get("OWNER_ID", "961369378"))
channelId = os.environ.get("CHANNEL_ID", "")
webhookUrl = os.environ.get("WEBHOOK_URL", "")
port = int(os.environ.get("PORT", "8080"))
webhookPath = "/webhook"
dbPath = os.environ.get("DB_PATH", "vaultguard.db")
botName = "VaultGuard"