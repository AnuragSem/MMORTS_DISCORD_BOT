import json
from bot.config_loader import EVENTS_PATH, TIPS_PATH
from bot.utils.helpers import validate_event_day
from bot.logger import setup_logging

logger = setup_logging("storage")

# ─── Event Handling ──────────────────────────────────────────────────────────
def load_all_events():
    try:
        with open(EVENTS_PATH, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                logger.warning("⚠️ events.json is in legacy format (list).")
                return {"default": data}
            return data
    except Exception as e:
        logger.error(f"❌ Failed to load events.json: {e}")
        return {}

def save_all_events(events):
    try:
        with open(EVENTS_PATH, "w") as f:
            json.dump(events, f, indent=4)
        logger.info("💾 Saved events.json")
    except Exception as e:
        logger.error(f"❌ Failed to save events.json: {e}")

def get_guild_events(events_dict, guild_id: str) -> list:
    return events_dict.setdefault(guild_id, [])

# ─── Tip Handling ────────────────────────────────────────────────────────────
def load_all_tips():
    try:
        with open(TIPS_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"⚠️ Failed to load tips.json: {e}")
        return {}

def save_all_tips(tip_dict):
    try:
        with open(TIPS_PATH, "w") as f:
            json.dump(tip_dict, f, indent=4)
        logger.info("💾 Saved tips.json")
    except Exception as e:
        logger.error(f"❌ Failed to save tips.json: {e}")

def get_guild_tips(tip_dict, guild_id: str) -> list:
    return tip_dict.setdefault(guild_id, [])

# ─── Cleanup Legacy ──────────────────────────────────────────────────────────
def cleanup_invalid_event_days(events_dict):
    for gid, events in events_dict.items():
        events_dict[gid] = [
            e for e in events if e.get("type") != "normal" or validate_event_day(e.get("day", ""))
        ]
