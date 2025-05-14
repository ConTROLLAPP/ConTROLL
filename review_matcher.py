def analyze_review_text(text):
    return {
        "tone": "Negative" if "awful" in text.lower() else "Neutral",
        "risk_score": 60 if "awful" in text.lower() else 10,
        "matched_guest": None,
        "alias": None,
        "style_match": 0,
        "created_ghost_guest": True
    }