import os
import json
from dotenv import load_dotenv
from bot.logger import setup_logging

logger = setup_logging("config")

# Load environment variables from .env
load_dotenv()
TOKEN = os.getenv("DISCORDBOT_TOKEN")

# JSON file paths
CONFIG_PATH = "config.json"
EVENTS_PATH = "events.json"
TIPS_PATH = "tips.json"

# ─── Config Loaders ─────────────────────────────────────────────────────────
def load_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
            logger.info("✅ Loaded config.json")
            return config
    except Exception as e:
        logger.warning(f"⚠️ Failed to load config.json: {e}")
        return {"channels": {}, "server_offsets": {}, "user_timezones": {}}

def save_config(config):
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=4)
        logger.info("💾 Saved config.json")
    except Exception as e:
        logger.error(f"❌ Failed to save config.json: {e}")
