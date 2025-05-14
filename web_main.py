from flask import Flask, request, jsonify
import os
import json
from datetime import datetime
from PIL import Image
import pytesseract

from main import (
    scan_new_guest, upload_screenshot, view_guest_queue,
    paste_review, manually_tag_alias, convert_ghost_guest,
    view_cold_match_pool, submit_shared_guest_note,
    load_guest_db
)

# Set persistent disk paths
DATA_DIR = "/data"
GUEST_DB_FILE = os.path.join(DATA_DIR, "guest_db.json")
SHARED_FILE = os.path.join(DATA_DIR, "shared_contributions.json")
COLD_MATCH_FILE = os.path.join(DATA_DIR, "cold_match_pool.json")

app = Flask(__name__)

@app.route("/")
def index():
    return "ConTROLL is running."

@app.route("/scan", methods=["POST"])
def scan_guest():
    data = request.json
    name = data.get("name", "")
    email = data.get("email", "")
    phone = data.get("phone", "")
    party_size = data.get("party_size", "1")

    profile = scan_new_guest(name, email, phone, party_size)
    return jsonify(profile)

@app.route("/ocr", methods=["POST"])
def ocr_upload():
    if "image" not in request.files:
        return jsonify({"error": "No image file uploaded"}), 400

    image_file = request.files["image"]
    img = Image.open(image_file)
    text = pytesseract.image_to_string(img)

    return jsonify({"extracted_text": text})

@app.route("/queue", methods=["GET"])
def guest_queue():
    try:
        db = load_guest_db()
        return jsonify(db)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))