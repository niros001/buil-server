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


@app.route("/")
def index():
    return jsonify(status="OK", message="Backend is alive")


@app.route('/api/convert', methods=['POST'])
def handle_pdf_to_vision():
    if 'pdf' not in request.files:
        return jsonify({'columns': [], 'rows': []})

    pdf_file = request.files['pdf']
    pdf_id = str(uuid.uuid4())
    pdf_path = os.path.join(UPLOAD_FOLDER, f"{pdf_id}.pdf")
    image_path = os.path.join(UPLOAD_FOLDER, f"{pdf_id}.png")

    try:
        # Save PDF to disk
        pdf_file.save(pdf_path)

        # Convert first page of PDF to image (DPI 100)
        images = convert_from_path(pdf_path, dpi=100)
        if not images:
            raise Exception("PDF conversion returned no images.")
        images[0].save(image_path, 'PNG')

        # Read and encode image to base64
        with open(image_path, "rb") as img_file:
            base64_image = base64.b64encode(img_file.read()).decode("utf-8")

        # Get selected option
        option = request.form.get("option", "basic")

        # Prompt variations
        prompt_by_option = {
            "basic": (
                "טבלה עם העמודות הבאות: איזור תוכנית, תיאור, כמות, יחידת מדידה, "
                "עלות משוערת מוצר, סה\"כ. תציג את המידע בטבלה לפי תוכנית העבודה בתמונה ששלחתי לך. "
                "נא להתייחס לעמודה של הכמות לאחר חישוב ובהתאם לאופני המדידה הקיימים "
                "ובהתאם ליחידות המדידה הנהוגים לכל אלמנט ואין צורך להראות את החישוב."
            ),
            "extended": (
                "בבקשה הפק טבלה מפורטת הכוללת את העמודות: איזור תוכנית, תיאור מפורט של הפריט, "
                "יחידת מדידה תקנית (כמו מ', מ\"ר, יח'), כמות מדויקת, מחיר משוער ליחידה, וסך כולל. "
                "נא ודא שכל הנתונים מתואמים לתוכנית המצורפת, לפי הבנתך הוויזואלית בלבד."
            ),
            "engineering": (
                "בהתבסס על תוכנית העבודה המצורפת, אנא בנה טבלת כמויות הנדסית. "
                "הטבלה תכיל את השדות הבאים: מק\"ט, תיאור רכיב, מיקום בתוכנית, יחידת מדידה, "
                "כמות, עלות ליחידה, עלות כוללת. אל תכלול חישובים גלויים – רק את התוצאה הסופית לכל שורה."
            )
        }

        full_prompt = (
            f"{prompt_by_option.get(option, prompt_by_option['basic'])} "
            "קרא את המידע מתמונה שצורפה. החזר אך ורק JSON תקני בפורמט הבא – ללא שום הסברים, תוספות או טקסט נוסף:"
            "{\"columns\": [\"...\"], \"rows\": [[\"...\"], [\"...\"]]}"
        )

        # Call OpenAI GPT-4 Vision
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": full_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                    ]
                }
            ],
            max_tokens=3000
        )

        result_text = response.choices[0].message.content.strip()

        # Attempt to parse as JSON
        try:
            result_json = json.loads(result_text)
            columns = result_json.get("columns", [])
            rows = result_json.get("rows", [])
            return jsonify({"columns": columns, "rows": rows})
        except Exception:
            return jsonify({"columns": [], "rows": []})

    except Exception as e:
        print("Error:", e)
        return jsonify({"columns": [], "rows": []})

    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        if os.path.exists(image_path):
            os.remove(image_path)


if __name__ == '__main__':
    app.run(port=5000)
