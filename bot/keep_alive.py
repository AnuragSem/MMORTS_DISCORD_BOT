from flask import Flask, jsonify
from threading import Thread
import logging
import datetime

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

@app.route("/")
def home():
    logging.info("✅ Ping received on root route.")
    return "Bot is alive!", 200

@app.route("/status")
def status():
    now = datetime.datetime.utcnow().isoformat() + "Z"
    logging.info("📡 Status check at %s", now)
    return jsonify({"status": "alive", "timestamp": now}), 200

def run():
    try:
        logging.info("🚀 Starting keep-alive server on port 8080")
        app.run(host="0.0.0.0", port=8080, threaded=True)
    except Exception as e:
        logging.error(f"❌ Keep-alive server failed: {e}")

def keep_alive():
    t = Thread(target=run)
    t.daemon = True  # Ensure thread exits on shutdown
    t.start()
