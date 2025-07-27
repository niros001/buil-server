import os
import uuid
import base64
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from pdf2image import convert_from_path
from openai import OpenAI
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from dotenv import load_dotenv

# Load .env if available
load_dotenv()

app = Flask(__name__)
CORS(app, origins=["*"])  # Accept all origins for testing
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.route("/api/convert", methods=["POST"])
def handle_pdf():
    if 'pdf' not in request.files:
        return jsonify({'error': 'Missing PDF file'}), 400

    # Save PDF to disk
    pdf_file = request.files['pdf']
    pdf_id = str(uuid.uuid4())
    pdf_path = os.path.join(UPLOAD_FOLDER, f"{pdf_id}.pdf")
    img_path = os.path.join(UPLOAD_FOLDER, f"{pdf_id}.png")
    output_pdf_path = os.path.join(UPLOAD_FOLDER, f"{pdf_id}_output.pdf")
    pdf_file.save(pdf_path)

    # Convert first page to image
    images = convert_from_path(pdf_path, dpi=100)
    if not images:
        raise Exception("PDF conversion failed")
    images[0].save(img_path, 'PNG')

    with open(img_path, "rb") as img:
        b64_image = base64.b64encode(img.read()).decode("utf-8")

    selected_option = request.form.get("option", "basic")

    base_prompt = (
        "תייצר לי קובץ pdf שמכיל טבלה עם העמודות הבאות: איזור תוכנית, תיאור, כמות, יחידת מדידה,"
        "עלות משוערת מוצר, סה\"כ. תציג את המידע בטבלה לפי תוכנית העבודה בתמונה ששלחתי לך."
        " נא להתייחס לעמודה של הכמות לאחר חישוב ובהתאם לאופני המדידה הקיימים ובהתאם ליחידות המדידה הנהוגים."
    )

    prompt_variants = {
        "basic": " תתייחס רק לריצוף וכרגע אל תחזיר באמת pdf אלה טקסט בלבד.",
        "simple": " אין צורך להראות את החישוב. תוריד עמודות מיותרות.",
        "calculated": " ותוסיף עמודה של חישוב שתראה דרך חישוב."
    }
    full_prompt = base_prompt + prompt_variants.get(selected_option, "")

    # Send to OpenAI
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
    result_text = response.choices[0].message.content

    # Create output PDF from text
    c = canvas.Canvas(output_pdf_path, pagesize=A4)
    y = 800
    for line in result_text.split('\n'):
        c.drawString(40, y, line.strip())
        y -= 20
    c.save()

    os.remove(pdf_path)
    os.remove(img_path)

    return send_file(output_pdf_path, mimetype='application/pdf')

if __name__ == "__main__":
    app.run(port=5000)
