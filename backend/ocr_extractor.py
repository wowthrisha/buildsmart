import anthropic
import base64
import json
import os


def extract_dimensions_from_image(image_bytes: bytes, media_type: str = "image/jpeg") -> dict:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    prompt = """You are analyzing a building sketch or notes for a Tamil Nadu building plan.
Extract every visible measurement. Return ONLY valid JSON with no explanation:
{
  "road_width_ft": <number or null>,
  "plot_width_ft": <number or null>,
  "plot_depth_ft": <number or null>,
  "plot_area_sqm": <number or null>,
  "proposed_floors": <integer 1-5 or null>,
  "building_type": <"residential" or "commercial" or null>,
  "front_setback_m": <number or null>,
  "rear_setback_m": <number or null>,
  "side_setback_m": <number or null>,
  "proposed_height_m": <number or null>,
  "proposed_builtup_sqm": <number or null>,
  "footprint_sqm": <number or null>,
  "confidence": {
    "road_width_ft": <"high","medium","low","not_found">,
    "plot_width_ft": <"high","medium","low","not_found">,
    "plot_depth_ft": <"high","medium","low","not_found">,
    "proposed_floors": <"high","medium","low","not_found">,
    "building_type": <"high","medium","low","not_found">
  },
  "missing_fields": ["field_name_1", "field_name_2"],
  "notes": "<what you saw and could not read>"
}
Rules:
- 30x40 means width=30ft depth=40ft
- G+1 means 2 floors, G+2 means 3 floors
- Convert feet to metres where needed (1ft=0.3048m)
- If dimension is unclear mark confidence as low and include in missing_fields
- Return null for anything not visible
- Return ONLY the JSON object, nothing else"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_b64,
                    },
                },
                {"type": "text", "text": prompt}
            ],
        }]
    )

    text = message.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "error": "Could not parse image",
            "missing_fields": ["road_width_ft", "plot_width_ft", "plot_depth_ft",
                               "proposed_floors", "building_type", "front_setback_m",
                               "rear_setback_m", "side_setback_m"],
            "notes": "Image quality too low or no dimensions visible"
        }


def generate_smart_questions(extracted: dict) -> list:
    field_questions = {
        "road_width_ft": {
            "question": "What is the road width in front of your plot?",
            "type": "select",
            "options": ["10", "12", "15", "20", "24", "30", "40"],
            "unit": "feet"
        },
        "proposed_floors": {
            "question": "How many floors are you planning?",
            "type": "select",
            "options": ["1 (Ground only)", "2 (G+1)", "3 (G+2)", "4 (G+3)"],
            "unit": ""
        },
        "front_setback_m": {
            "question": "What front setback are you planning?",
            "type": "number",
            "unit": "metres"
        },
        "rear_setback_m": {
            "question": "What is the rear setback (distance from rear boundary)?",
            "type": "number",
            "unit": "metres"
        },
        "side_setback_m": {
            "question": "What is the side setback (distance from side boundary)?",
            "type": "number",
            "unit": "metres"
        },
        "proposed_height_m": {
            "question": "What is the proposed building height?",
            "type": "number",
            "unit": "metres"
        },
        "plot_width_ft": {
            "question": "What is your plot width?",
            "type": "number",
            "unit": "feet"
        },
        "plot_depth_ft": {
            "question": "What is your plot depth?",
            "type": "number",
            "unit": "feet"
        },
        "building_type": {
            "question": "What is the building use?",
            "type": "select",
            "options": ["residential", "commercial"],
            "unit": ""
        }
    }

    questions = []
    missing = extracted.get("missing_fields", [])
    confidence = extracted.get("confidence", {})

    for field in missing:
        if field in field_questions and len(questions) < 3:
            q = field_questions[field].copy()
            q["field"] = field
            q["current_value"] = None
            questions.append(q)

    for field, conf in confidence.items():
        if conf == "low" and field not in missing and len(questions) < 3:
            if field in field_questions:
                q = field_questions[field].copy()
                q["field"] = field
                q["question"] = f"Please confirm: {q['question']}"
                q["current_value"] = extracted.get(field)
                questions.append(q)

    return questions
