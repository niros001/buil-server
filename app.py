from flask import Flask, request, jsonify
from flask_cors import CORS
from pdf2image import convert_from_bytes
from openai import OpenAI
from dotenv import load_dotenv
import base64
import os
import io

load_dotenv()

app = Flask(__name__)
CORS(app, origins=["https://buil-client.netlify.app", "http://localhost:5173"], supports_credentials=True)

openai_api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key)


@app.route("/")
def index():
    return jsonify(status="OK", message="Backend is alive")


@app.route('/api/convert', methods=['POST'])
def handle_pdf_to_vision():
    if 'pdf' not in request.files:
        return jsonify({'error': 'No PDF file provided'}), 400

    pdf_file = request.files['pdf']
    main_option = request.form.get('main_option')
    free_text = request.form.get('free_text', '')

    # קובע את הפרומפט לפי הבחירה
    user_prompt = free_text if main_option == 'custom' else "מה המצב?? שכחתי לכתוב לך שאלה"

    try:
        # קורא את התוכן של הקובץ כ-bytes
        pdf_bytes = pdf_file.read()

        # ממיר את ה-PDF לתמונה בזיכרון
        images = convert_from_bytes(pdf_bytes, dpi=150)
        if not images:
            raise Exception("PDF conversion returned no images.")

        # שמירה של התמונה הראשונה כ-JPEG בזיכרון
        image_io = io.BytesIO()
        images[0].save(image_io, format="JPEG", quality=85)
        image_io.seek(0)
        base64_image = base64.b64encode(image_io.read()).decode("utf-8")

        # שליחה ל-GPT עם התמונה
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        }
                    ]
                }
            ],
            max_tokens=3000
        )

        result_text = response.choices[0].message.content
        return jsonify({'result': result_text})

    except Exception as e:
        print("Error:", e)
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(port=5000)
