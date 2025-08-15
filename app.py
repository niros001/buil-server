import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
import base64

load_dotenv()

app = Flask(__name__)
CORS(app, origins=["https://buil-client.netlify.app", "http://localhost:5173"], supports_credentials=True)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@app.route("/")
def index():
    return jsonify(status="OK", message="Backend is alive")


@app.route('/api/convert', methods=['POST'])
def handle_pdf_to_vision():
    if 'pdf' not in request.files:
        return jsonify({'error': 'No PDF file provided'}), 400

    pdf_file = request.files['pdf']
    free_text = request.form.get('free_text', '')

    try:
        pdf_bytes = pdf_file.read()
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')

        user_prompt = free_text if free_text else "אנא קרא את ה-PDF וסכם עבורי את התוכן"

        response = client.chat.completions.create(
            model="gpt-5",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "file",
                            "file_name": pdf_file.filename,
                            "file_content_base64": pdf_base64
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
