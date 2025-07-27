import os
import uuid
import base64
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from pdf2image import convert_from_path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@app.route("/api/convert", methods=["POST"])
def handle_pdf():
    if 'pdf' not in request.files:
        return jsonify({'error': 'Missing PDF file'}), 400

    pdf_file = request.files['pdf']

    # 🔽 קבלת שלושת השדות מה-form
    option = request.form.get('option', 'basic')
    element_options = request.form.get('element_options', '')
    additional_options = request.form.get('additional_options', '')

    pdf_id = str(uuid.uuid4())
    pdf_path = os.path.join(UPLOAD_FOLDER, f"{pdf_id}.pdf")
    img_path = os.path.join(UPLOAD_FOLDER, f"{pdf_id}.png")
    pdf_file.save(pdf_path)

    images = convert_from_path(pdf_path, dpi=100)
    if not images:
        return jsonify({'error': 'PDF conversion failed'}), 500
    images[0].save(img_path, 'PNG')

    with open(img_path, "rb") as img:
        b64_image = base64.b64encode(img.read()).decode("utf-8")

    prompt_by_option = {
        "basic": "תפיק טבלה עם העמודות: איזור תוכנית, תיאור, כמות.",
        "simple": "תפיק טבלה עם העמודות: איזור תוכנית, תיאור, כמות, יחידת מדידה.",
        "calculated": "תפיק טבלה עם העמודות: איזור תוכנית, תיאור, כמות, יחידת מדידה, עלות משוערת ליחידה, סה\"כ."
    }

    full_prompt = (
        f"{prompt_by_option.get(option, prompt_by_option['basic'])} "
        "השתמש בתמונה שצירפתי שמכילה תוכנית עבודה. החזר רק JSON בפורמט הבא: "
        "{ \"columns\": [\"...\"], \"rows\": [[\"...\"], [\"...\"]] }"
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": full_prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_image}"}}
            ]
        }],
        max_tokens=3000
    )

    result_text = response.choices[0].message.content.strip()

    try:
        if result_text.startswith("```json"):
            result_text = result_text.strip("`\n ").replace("json", "", 1).strip()
        parsed_json = json.loads(result_text)
    except Exception as e:
        return jsonify({'error': 'Failed to parse GPT output', 'raw': result_text, 'details': str(e)}), 500

    os.remove(pdf_path)
    os.remove(img_path)

    return jsonify(parsed_json)


if __name__ == "__main__":
    app.run(port=5000)
