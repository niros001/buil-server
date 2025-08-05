import io
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
from pdf2image import convert_from_bytes
from PIL import Image
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
CORS(app, origins=["https://buil-client.netlify.app", "http://localhost:5173"], supports_credentials=True)

openai_api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key)


def pdf_to_one_long_image_base64(pdf_bytes, dpi=200):
    images = convert_from_bytes(pdf_bytes, dpi=dpi)
    print(f"Number of images/pages in PDF: {len(images)}")  # הדפסת מספר התמונות

    if not images:
        raise Exception("PDF conversion returned no images.")

    width, height = images[0].size
    total_height = height * len(images)

    combined_img = Image.new('RGB', (width, total_height), (255, 255, 255))

    for i, img in enumerate(images):
        combined_img.paste(img, (0, i * height))

    img_buffer = io.BytesIO()
    combined_img.save(img_buffer, format='PNG')  # שמירה כ-PNG
    img_buffer.seek(0)

    return base64.b64encode(img_buffer.read()).decode('utf-8')


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
        pdf_bytes = pdf_file.read()
        base64_image = pdf_to_one_long_image_base64(pdf_bytes, dpi=200)

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{base64_image}"}
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
