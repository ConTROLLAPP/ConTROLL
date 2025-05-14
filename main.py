import time
import json
import os
import re
from datetime import datetime
from PIL import Image
import pytesseract
from search_utils import run_full_guest_search
from review_matcher import analyze_review_text
from star_rating import get_star_rating, update_star_rating
from guest_notes import get_shared_notes, add_guest_note
from stylometry import compare_writing_style
from api_usage_tracker import check_api_quota

SHARED_FILE = "shared_contributions.json"
GUEST_DB_FILE = "guest_db.json"

# === Registry and Shared Notes ===
def load_registry():
    with open("restaurant_registry.json", "r") as f:
        return json.load(f)

def choose_restaurant_id():
    registry = load_registry()
    print("\nSelect your restaurant location:")
    for idx, (rid, name) in enumerate(registry.items(), 1):
        print(f"{idx}. {rid} — {name}")
    try:
        choice = int(input("Enter choice number: "))
        selected_id = list(registry.keys())[choice - 1]
        return selected_id
    except (IndexError, ValueError):
        print("Invalid choice. Defaulting to first entry.")
        return list(registry.keys())[0]

def load_shared_contributions():
    if not os.path.exists(SHARED_FILE):
        return {}
    with open(SHARED_FILE, "r") as f:
        return json.load(f)

def save_shared_contribution(guest_name, note):
    shared = load_shared_contributions()
    if guest_name not in shared:
        shared[guest_name] = []
    shared[guest_name].append(note)
    with open(SHARED_FILE, "w") as f:
        json.dump(shared, f, indent=4)

# === Guest DB ===
def load_guest_db():
    if not os.path.exists(GUEST_DB_FILE):
        return {}
    with open(GUEST_DB_FILE, "r") as f:
        return json.load(f)

def save_guest_db(db):
    with open(GUEST_DB_FILE, "w") as f:
        json.dump(db, f, indent=4)

def scan_new_guest():
    name = input("Enter guest full name: ")
    email = input("Enter guest email address: ")
    phone = input("Enter guest phone number (optional): ")
    party_size = input("Enter number in guest's party: ")

    check_api_quota()

    print("\n\U0001F6E1️ Checking public risk mentions...")
    guest_profile = run_full_guest_search(name, email, phone)
    risk_score = guest_profile.get("risk_score", 0)
    style_match = guest_profile.get("style_match", 0)
    keywords = guest_profile.get("keywords", [])
    matched_platforms = guest_profile.get("matched_platforms", [])

    if risk_score >= 80:
        star_rating = 1
    elif risk_score >= 60:
        star_rating = 2
    elif risk_score >= 40:
        star_rating = 3
    elif risk_score >= 20:
        star_rating = 4
    else:
        star_rating = 5

    shared_notes = get_shared_notes(name)

    guest_data = {
        "email": email,
        "phone": phone,
        "party_size": party_size,
        "risk_score": risk_score,
        "style_match": style_match,
        "keywords": keywords,
        "star_rating": star_rating,
        "notes": shared_notes,
        "matched_platforms": matched_platforms,
        "alias_reviews": [],
        "visit_history": [{
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "location": choose_restaurant_id()
        }]
    }

    db = load_guest_db()
    db[name] = guest_data
    save_guest_db(db)

    risk_color = ""
    if risk_score >= 80:
        risk_color = "\U0001F534 HIGH"
    elif risk_score >= 40:
        risk_color = "\U0001F7E1 MEDIUM"
    elif risk_score > 0:
        risk_color = "\U0001F7E2 LOW"

    print("\n✅ Guest Saved:")
    print(f"Name: {name}")
    print(f"Risk Score: {risk_score} ({risk_color})")
    print(f"Style Match: {style_match}%")
    print(f"Keywords: {keywords}")
    print(f"Star Rating: {star_rating} ⭐")
    if matched_platforms:
        print("Matched Platforms:")
        for match in matched_platforms:
            print(f"- {match}")
        if len(matched_platforms) >= 2 and risk_score >= 30:
            print("⚠️ ALERT: Multiple platforms flagged this guest — Possible viral or reputation risk")
    if shared_notes:
        print(f"Shared Notes: {shared_notes}")
# === Part 2 of 2 ===

def view_guest_queue():
    db = load_guest_db()
    if not db:
        print("\nGuest queue is empty.")
        return
    print("\n--- Guest Queue ---")
    for name, info in db.items():
        print(f"\n{name} | Risk: {info['risk_score']} | Stars: {info['star_rating']} ⭐")
        print(f"Notes: {info['notes']}")
        print(f"Keywords: {info['keywords']}")
        if info.get("alias_reviews"):
            print("Alias Reviews:")
            for entry in info["alias_reviews"]:
                print(f"- {entry['alias']}: {entry['text']}")
        if info.get("visit_history"):
            print("Visit History:")
            for visit in info["visit_history"]:
                print(f"  • {visit}")

        if info.get("alias_memory"):
            print("Alias Memory:")
            for alias, entries in info["alias_memory"].items():
                print(f"- {alias}:")
                for entry in entries:
                    print(f"    • {entry['source']} — {entry['text']}")
        if info.get("matched_platforms"):
            print("Matches:")
            for match in info["matched_platforms"]:
                print(f"- {match}")

# Add OCR Upload Feature
from PIL import Image
import pytesseract

def upload_screenshot():
    print("\n\U0001F4C2 Upload a screenshot of the reservation (Resy, etc.)")
    file_path = input("Enter path to image file (e.g., screenshot.png): ").strip()

    if not os.path.exists(file_path):
        print("❌ File not found.")
        return

    try:
        text = pytesseract.image_to_string(Image.open(file_path))
        print("\n--- OCR Extracted Text ---")
        print(text)

        name, email, phone, party_size = "", "", "", ""
        lines = text.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if not email and "@" in line and "." in line:
                email = line
            if not phone and re.search(r"(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})", line):
                phone = re.search(r"(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})", line).group(1)
            if not party_size and re.search(r"(party of|table for|guests?)\s+(\d+)", line.lower()):
                party_size = re.search(r"(party of|table for|guests?)\s+(\d+)", line.lower()).group(2)
            if not name and any(word in line.lower() for word in ["guest", "name", "resy"]):
                parts = line.split(":")
                if len(parts) > 1:
                    name = parts[-1].strip()

        if not name:
            name = input("Enter guest name (OCR unclear): ").strip()
        if not email:
            email = input("Enter guest email (OCR unclear): ").strip()
        if not phone:
            phone = input("Enter guest phone (OCR unclear): ").strip()
        if not party_size:
            party_size = input("Enter party size (OCR unclear): ").strip()

        print(f"\U0001F9E0 Scanning extracted guest: {name} — {email}")
        check_api_quota()
        guest_profile = run_full_guest_search(name, email, phone)

        risk_score = guest_profile.get("risk_score", 0)
        style_match = guest_profile.get("style_match", 0)
        keywords = guest_profile.get("keywords", [])
        matched_platforms = guest_profile.get("matched_platforms", [])
        shared_notes = get_shared_notes(name)

        guest_data = {
            "email": email,
            "phone": phone,
            "party_size": party_size,
            "risk_score": risk_score,
            "style_match": style_match,
            "keywords": keywords,
            "star_rating": get_star_rating(risk_score),
            "notes": shared_notes,
            "matched_platforms": matched_platforms,
            "alias_reviews": [],
            "visit_history": [{
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "location": choose_restaurant_id()
            }]
        }

        db = load_guest_db()
        db[name] = guest_data
        save_guest_db(db)

        print("\n✅ OCR Guest Scanned:")
        print(f"Name: {name}")
        print(f"Risk Score: {risk_score}")
        print(f"Phone: {phone}")
        print(f"Party Size: {party_size}")
        print(f"Keywords: {keywords}")
        if matched_platforms:
            print("Matched Platforms:")
            for m in matched_platforms:
                print(f"  - {m}")

    except Exception as e:
        print(f"❌ OCR failed: {e}")
def view_guest_queue():
    db = load_guest_db()
    if not db:
        print("\nGuest queue is empty.")
        return
    print("\n--- Guest Queue ---")
    for name, info in db.items():
        print(f"\n{name} | Risk: {info['risk_score']} | Stars: {info['star_rating']} ⭐")
        print(f"Notes: {info['notes']}")
        print(f"Keywords: {info['keywords']}")
        if info.get("alias_reviews"):
            print("Alias Reviews:")
            for entry in info["alias_reviews"]:
                print(f"- {entry['alias']}: {entry['text']}")
        if info.get("visit_history"):
            print("Visit History:")
            for visit in info["visit_history"]:
                print(f"  • {visit}")

        if info.get("alias_memory"):
            print("Alias Memory:")
            for alias, entries in info["alias_memory"].items():
                print(f"- {alias}:")
                for entry in entries:
                    print(f"    • {entry['source']} — {entry['text']}")
        if info.get("matched_platforms"):
            print("Matches:")
            for match in info["matched_platforms"]:
                print(f"- {match}")

def paste_review():
    print("\nPaste the full bad review text below. Then press Enter and wait for analysis:\n")
    review_text = input(">>> ")
    result = analyze_review_text(review_text)

    print("\n--- Analysis Result ---")
    print(f"Tone of Review: {result['tone']}")
    print(f"Estimated Risk Score: {result['risk_score']}")
    if result.get("matched_guest"):
        print(f"Matched Guest: {result['matched_guest']} — Style Match: {result['style_match']}%")
    elif result.get("created_ghost_guest"):
        print(f"Ghost profile created for alias: {result['alias']} — Stylometry: {result['style_match']}%")
    else:
        print("No identity match found. Recommend monitoring for further patterns.")
def manually_tag_alias():
    db = load_guest_db()
    alias = input("Enter the alias used in the review (e.g., @FoodieCritic42): ")
    real_name = input("Enter the real guest name this alias belongs to: ")
    review_text = input("Paste the review text (optional): ")

    if real_name not in db:
        print("Guest not found in database. Try again after scanning them in.")
        return

    if "alias_reviews" not in db[real_name]:
        db[real_name]["alias_reviews"] = []

    db[real_name]["alias_reviews"].append({
        "alias": alias,
        "text": review_text,
        "verified": True
    })

    if "alias_memory" not in db[real_name]:
        db[real_name]["alias_memory"] = {}
    if alias not in db[real_name]["alias_memory"]:
        db[real_name]["alias_memory"][alias] = []

    db[real_name]["alias_memory"][alias].append({
        "text": review_text,
        "source": "Manual Tag"
    })

    note = f"Alias {alias} linked manually to this guest after confirmed review."
    db[real_name]["notes"] += " | " + note
    save_guest_db(db)
    print(f"✅ Alias {alias} tagged to {real_name} and saved.")

def convert_ghost_guest():
    db = load_guest_db()
    ghost_keys = [key for key in db.keys() if key.startswith("ghost_")]

    if not ghost_keys:
        print("\nNo ghost guests found.")
        return

    print("\n--- Ghost Guests ---")
    for idx, key in enumerate(ghost_keys, 1):
        print(f"{idx}. {key}")

    try:
        selection = int(input("Select a ghost guest to convert (number): "))
        ghost_key = ghost_keys[selection - 1]
    except (ValueError, IndexError):
        print("Invalid selection.")
        return

    real_name = input("Enter real guest name: ")
    email = input("Enter email: ")
    phone = input("Enter phone number: ")
    party_size = input("Enter party size: ")

    ghost_data = db.pop(ghost_key)
    guest_data = {
        "email": email,
        "phone": phone,
        "party_size": party_size,
        "risk_score": ghost_data.get("risk_score", 0),
        "style_match": ghost_data.get("style_match", 0),
        "keywords": ghost_data.get("keywords", []),
        "star_rating": ghost_data.get("star_rating", 3),
        "notes": f"Converted from ghost guest {ghost_key}",
        "matched_platforms": [],
        "alias_reviews": [],
        "last_review": ghost_data.get("last_review", ""),
        "tone": ghost_data.get("tone", "Unknown")
    }

    db[real_name] = guest_data
    save_guest_db(db)
    print(f"✅ Ghost guest {ghost_key} converted to {real_name}.")

def view_cold_match_pool():
    pool_file = "cold_match_pool.json"
    if not os.path.exists(pool_file):
        print("\nNo cold match pool found.")
        return

    with open(pool_file, "r") as f:
        reviews = json.load(f)

    if not reviews:
        print("\nCold match pool is empty.")
        return

    db = load_guest_db()
    updated_reviews = []

    print("\n--- Cold Match Pool ---")
    for idx, entry in enumerate(reviews, 1):
        print(f"\n#{idx}")
        print(f"📝 Review: {entry['text']}")
        print(f"🟡 Tone: {entry.get('tone', 'Unknown')}")
        print(f"🔑 Keywords: {', '.join(entry.get('keywords', []))}")
        tag = input("Tag this review to a guest? (y/n): ").strip().lower()
        if tag == "y":
            alias = input("Enter alias used in review (e.g., @KarenSnaps): ").strip()
            real_name = input("Enter real guest name: ").strip()
            if real_name not in db:
                print("Guest not found. Please scan them first (Option 1).")
                updated_reviews.append(entry)
                continue
            if "alias_reviews" not in db[real_name]:
                db[real_name]["alias_reviews"] = []
            db[real_name]["alias_reviews"].append({
                "alias": alias,
                "text": entry["text"],
                "verified": True
            })

            if "alias_memory" not in db[real_name]:
                db[real_name]["alias_memory"] = {}
            if alias not in db[real_name]["alias_memory"]:
                db[real_name]["alias_memory"][alias] = []
            db[real_name]["alias_memory"][alias].append({
                "text": entry["text"],
                "source": "Cold Pool Tag"
            })
            note = f"Alias {alias} linked from Cold Pool to this guest."
            db[real_name]["notes"] += " | " + note
            print(f"✅ Tagged and removed from Cold Match Pool.")
        else:
            updated_reviews.append(entry)

    save_guest_db(db)
    with open(pool_file, "w") as f:
        json.dump(updated_reviews, f, indent=4)
import time
import json
import os
import re
from datetime import datetime
from PIL import Image
import pytesseract
from search_utils import run_full_guest_search
from review_matcher import analyze_review_text
from star_rating import get_star_rating, update_star_rating
from guest_notes import get_shared_notes, add_guest_note
from stylometry import compare_writing_style
from api_usage_tracker import check_api_quota

SHARED_FILE = "shared_contributions.json"
GUEST_DB_FILE = "guest_db.json"

# === Registry and Shared Notes ===
def load_registry():
    with open("restaurant_registry.json", "r") as f:
        return json.load(f)

def choose_restaurant_id():
    registry = load_registry()
    print("\nSelect your restaurant location:")
    for idx, (rid, name) in enumerate(registry.items(), 1):
        print(f"{idx}. {rid} — {name}")
    try:
        choice = int(input("Enter choice number: "))
        selected_id = list(registry.keys())[choice - 1]
        return selected_id
    except (IndexError, ValueError):
        print("Invalid choice. Defaulting to first entry.")
        return list(registry.keys())[0]

def load_shared_contributions():
    if not os.path.exists(SHARED_FILE):
        return {}
    with open(SHARED_FILE, "r") as f:
        return json.load(f)

def save_shared_contribution(guest_name, note):
    shared = load_shared_contributions()
    if guest_name not in shared:
        shared[guest_name] = []
    shared[guest_name].append(note)
    with open(SHARED_FILE, "w") as f:
        json.dump(shared, f, indent=4)

# === Guest DB ===
def load_guest_db():
    if not os.path.exists(GUEST_DB_FILE):
        return {}
    with open(GUEST_DB_FILE, "r") as f:
        return json.load(f)

def save_guest_db(db):
    with open(GUEST_DB_FILE, "w") as f:
        json.dump(db, f, indent=4)

# === OCR Upload Feature ===
def upload_screenshot():
    print("\n\U0001F4C2 Upload a screenshot of the reservation (Resy, etc.)")
    file_path = input("Enter path to image file (e.g., screenshot.png): ").strip()

    if not os.path.exists(file_path):
        print("❌ File not found.")
        return

    try:
        text = pytesseract.image_to_string(Image.open(file_path))
        print("\n--- OCR Extracted Text ---")
        print(text)

        name, email, phone, party_size = "", "", "", ""
        lines = text.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if not email and "@" in line and "." in line:
                email = line
            if not phone and re.search(r"(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})", line):
                phone = re.search(r"(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})", line).group(1)
            if not party_size and re.search(r"(party of|table for|guests?)\s+(\d+)", line.lower()):
                party_size = re.search(r"(party of|table for|guests?)\s+(\d+)", line.lower()).group(2)
            if not name and any(word in line.lower() for word in ["guest", "name", "resy"]):
                parts = line.split(":")
                if len(parts) > 1:
                    name = parts[-1].strip()

        if not name:
            name = input("Enter guest name (OCR unclear): ").strip()
        if not email:
            email = input("Enter guest email (OCR unclear): ").strip()
        if not phone:
            phone = input("Enter guest phone (OCR unclear): ").strip()
        if not party_size:
            party_size = input("Enter party size (OCR unclear): ").strip()

        print(f"\U0001F9E0 Scanning extracted guest: {name} — {email}")
        check_api_quota()
        guest_profile = run_full_guest_search(name, email, phone)

        risk_score = guest_profile.get("risk_score", 0)
        style_match = guest_profile.get("style_match", 0)
        keywords = guest_profile.get("keywords", [])
        matched_platforms = guest_profile.get("matched_platforms", [])
        shared_notes = get_shared_notes(name)

        guest_data = {
            "email": email,
            "phone": phone,
            "party_size": party_size,
            "risk_score": risk_score,
            "style_match": style_match,
            "keywords": keywords,
            "star_rating": get_star_rating(risk_score),
            "notes": shared_notes,
            "matched_platforms": matched_platforms,
            "alias_reviews": [],
            "visit_history": [{
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "location": choose_restaurant_id()
            }]
        }

        db = load_guest_db()
        db[name] = guest_data
        save_guest_db(db)

        print("\n✅ OCR Guest Scanned:")
        print(f"Name: {name}")
        print(f"Risk Score: {risk_score}")
        print(f"Phone: {phone}")
        print(f"Party Size: {party_size}")
        print(f"Keywords: {keywords}")
        if matched_platforms:
            print("Matched Platforms:")
            for m in matched_platforms:
                print(f"  - {m}")

    except Exception as e:
        print(f"❌ OCR failed: {e}")

def show_dev_roadmap():
    print("\n" + "="*50)
    print("     ConTROLL DEV ROADMAP — NEXT OBJECTIVES")
    print("="*50)
    print("1. Anonymous Reviewer Tagging")
    print("   - Paste review + assign real guest name")
    print("   - Save alias to guest notes")
    print()
    print("2. Star + Color Rating Finalization")
    print("   - Tighter score thresholds")
    print("   - Match stars to color code (🟢🟡🔴)")
    print()
    print("3. Ghost Guest Matching")
    print("   - Connect future reviews to ghosts")
    print("   - Prompt to convert ghost to real guest")
    print()
    print("4. Flow & Notes UX")
    print("   - Add manual guest notes")
    print("   - View/edit guests by name/email")
    print("   - Show aliases tied to reviews")
    print()
    print("STRETCH GOALS:")
    print("   - Screenshot OCR input")
    print("   - Cold match pool viewer")
    print("   - Handle memory for repeat aliases")
    print("="*50 + "\n")

def main():
    show_dev_roadmap()
    while True:
        print("\n--- Welcome to ConTROLL Dream Mode ---")
        print("1. Scan New Guest")
        print("2. View Guest Queue")
        print("3. Paste Bad Review for Analysis")
        print("4. Manually Tag Alias to Guest")
        print("5. Convert Ghost to Real Guest")
        print("6. View Cold Match Pool")
        print("7. Submit Shared Guest Note")
        print("8. Exit")
        print("9. Upload Screenshot (OCR)")

        choice = input("Enter choice (1/2/3/4/5/6/7/8/9): ")
        if choice == "1":
            scan_new_guest()
        elif choice == "2":
            view_guest_queue()
        elif choice == "3":
            paste_review()
        elif choice == "4":
            manually_tag_alias()
        elif choice == "5":
            convert_ghost_guest()
        elif choice == "6":
            view_cold_match_pool()
        elif choice == "7":
            submit_shared_guest_note()
        elif choice == "9":
            upload_screenshot()
        elif choice == "8":
            print("Exiting ConTROLL. Goodbye.")
            break
        else:
            print("Invalid choice. Try again.")

if __name__ == "__main__":
    main()
