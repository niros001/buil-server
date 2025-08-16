import io
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
import os

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
    user_prompt = free_text if main_option == 'custom' else "נתח את תוכנית הבנייה ותן כמויות חומרים"

    try:
        # מעלים את הקובץ לשרת של OpenAI
        uploaded_file = client.files.create(
            file=pdf_file,
            purpose="assistants"
        )

        # שולחים בקשה ל־GPT-5 עם ה־file_id
        response = client.chat.completions.create(
            model="gpt-5",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "file", "file": {"file_id": uploaded_file.id}}
                    ]
                }
            ],
            max_completion_tokens=5000
        )

        result_text = response.choices[0].message.content
        return jsonify({'result': result_text})

    except Exception as e:
        print("Error:", e)
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(port=5000)
