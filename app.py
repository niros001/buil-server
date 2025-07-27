import os
import uuid
import base64
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from pdf2image import convert_from_path
from openai import OpenAI
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

# Initialize Flask and CORS
app = Flask(__name__)
CORS(app, origins=["https://buil-client.netlify.app", "http://localhost:5173"], supports_credentials=True)

# Create folders
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize OpenAI client with API key
openai_api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key)


@app.route('/api/convert', methods=['POST'])
def handle_pdf_to_vision():
    if 'pdf' not in request.files:
        return jsonify({"columns": [], "rows": [], "error": "No PDF file provided"})

    pdf_file = request.files['pdf']
    pdf_id = str(uuid.uuid4())
    pdf_path = os.path.join(UPLOAD_FOLDER, f"{pdf_id}.pdf")
    image_path = os.path.join(UPLOAD_FOLDER, f"{pdf_id}.png")

    try:
        # Save PDF to disk
        pdf_file.save(pdf_path)

        # Convert first page of PDF to image (DPI 150)
        images = convert_from_path(pdf_path, dpi=150)
        if not images:
            raise Exception("PDF conversion returned no images.")
        images[0].save(image_path, 'PNG')

        # Read and encode image to base64
        with open(image_path, "rb") as img_file:
            base64_image = base64.b64encode(img_file.read()).decode("utf-8")

        # Get selected option (currently unused, but can be expanded)
        option = request.form.get("option", "basic")

        # Hardcoded prompt
        full_prompt = """
אתה שמאי בנייה מומחה שפועל עבור מערכת מקצועית, לא בן אדם. הוזנה תמונה של תוכנית בנייה, ועליך לנתח רק את המידע הגרפי בתמונה בלבד.

מטרתך היחידה: להחזיר טבלה בפורמט JSON תקני בלבד, עם הנתונים שאתה מזהה מתוך התוכנית. אל תבצע ניחושים ואל תשתמש בשום ידע חיצוני – אך אל תספק הסברים, תיאורים או טקסטים מחוץ למבנה JSON.

### דרישות פורמט JSON:

{
  "columns": ["איזור תוכנית", "תיאור", "כמות", "יחידת מדידה", "עלות משוערת מוצר", "סה\"כ"],
  "rows": [
    ["...", "...", "...", "...", "...", "..."],
    ["...", "...", "...", "...", "...", "..."]
  ]
}

הערות:

- החזר אך ורק את האובייקט JSON – בלי שום טקסט לפני או אחרי.
- במקרה שאינך מצליח לקרוא את הנתונים מהתמונה – החזר אובייקט ריק כך:
{
  "columns": [],
  "rows": []
}
- אין לכלול שום הערות, הסברים, או טקסטים – רק JSON נקי.
- עליך לפעול כמו מערכת אוטומטית שמחזירה מידע מובנה בלבד.
"""

        # Call OpenAI GPT-4 Vision
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "אתה מומחה בקריאת תוכניות בתחום הבנייה בפרט אלו הבנייה בישראל. אני רוצה שתמצא לי את כמות המטר הרבוע (רצפה) בכל מוקה של התוכנית שתקבל בתמונה. תביא את המספר המדוייק ככל שניתן עם סטיית תקן מינימלית אם לא תיהיה ברירה."},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                    ]
                }
            ],
            max_tokens=3000
        )

        result_text = response.choices[0].message.content.strip()

        print("GPT raw output:", result_text)

        try:
            result_json = json.loads(result_text)
            columns = result_json.get("columns", [])
            rows = result_json.get("rows", [])
            return jsonify({"columns": columns, "rows": rows, "error": None})
        except Exception as parse_err:
            return jsonify({
                "columns": [],
                "rows": [],
                "error": f"Failed to parse GPT output: {str(parse_err)}",
                "raw": result_text
            })

    except Exception as e:
        return jsonify({"columns": [], "rows": [], "error": str(e)})

    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        if os.path.exists(image_path):
            os.remove(image_path)


if __name__ == '__main__':
    app.run(port=5000)
