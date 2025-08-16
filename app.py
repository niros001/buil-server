import os
import io
from flask import Flask, request, jsonify
from flask_cors import CORS
from pdf2image import convert_from_bytes
import pytesseract
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

app = Flask(__name__)
CORS(app, origins=[
    "https://buil-client.netlify.app",
    "http://localhost:5173"
], supports_credentials=True)

openai_api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key)


@app.route("/")
def index():
    return jsonify(status="OK", message="Backend is alive")


@app.route("/api/convert", methods=["POST"])
def convert():
    if "pdf" not in request.files:
        return jsonify({"error": "No PDF file provided"}), 400

    pdf_file = request.files["pdf"]
    main_option = request.form.get("main_option")
    free_text = request.form.get(
        "free_text",
        "חשב לי את כמויות הברזל לפי התוכנית שה-PDF מצרף."
    )

    try:
        # המרת PDF לתמונות עמוד עמוד
        pdf_bytes = pdf_file.read()
        images = convert_from_bytes(pdf_bytes, dpi=150)  # DPI נמוך יותר לחיסכון בזיכרון
        extracted_text = ""

        for i, img in enumerate(images):
            # OCR עמוד אחד בכל פעם
            text = pytesseract.image_to_string(img, lang="heb+eng")
            extracted_text += f"\n\n--- Page {i+1} ---\n{text}"

        # שולח את הטקסט ל-GPT
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "user", "content": f"{free_text}\n\n{extracted_text}"}
            ],
            max_completion_tokens=3000
        )

        result_text = response.choices[0].message.content

        return jsonify({"result": result_text})

    except Exception as e:
        print("Error:", e)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(port=5000)
