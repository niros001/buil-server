import os
import uuid
import base64
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from pdf2image import convert_from_path
from openai import OpenAI
from dotenv import load_dotenv
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib import colors
from bidi.algorithm import get_display

# Load .env if available
load_dotenv()

app = Flask(__name__)
CORS(app, origins=["*"])
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

pdfmetrics.registerFont(
    TTFont('Hebrew', 'fonts/NotoSansHebrew-VariableFont_wdth,wght.ttf')
)


def process_rtl(text):
    return get_display(text)


def create_hebrew_table_pdf(path, text):
    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    styles = getSampleStyleSheet()
    hebrew_style = ParagraphStyle(
        name='Hebrew',
        parent=styles['Normal'],
        fontName='Hebrew',
        fontSize=12,
        alignment=TA_RIGHT
    )

    lines = [line.strip() for line in text.split("\n") if line.strip() and not line.startswith('|---')]
    table_data = [line.strip('|').split('|') for line in lines]

    if len(table_data) > 2:
        table_data = table_data[1:-1]

    formatted_data = [
        [Paragraph(process_rtl(cell.strip()), hebrew_style) for cell in reversed(row)]
        for row in table_data
    ]

    table = Table(formatted_data, hAlign='RIGHT')
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Hebrew'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
    ]))

    doc.build([table])


@app.route("/api/convert", methods=["POST"])
def handle_pdf():
    if 'pdf' not in request.files:
        return jsonify({'error': 'Missing PDF file'}), 400

    pdf_file = request.files['pdf']
    pdf_id = str(uuid.uuid4())
    pdf_path = os.path.join(UPLOAD_FOLDER, f"{pdf_id}.pdf")
    img_path = os.path.join(UPLOAD_FOLDER, f"{pdf_id}.png")
    output_pdf_path = os.path.join(UPLOAD_FOLDER, f"{pdf_id}_output.pdf")
    pdf_file.save(pdf_path)

    images = convert_from_path(pdf_path, dpi=100)
    if not images:
        raise Exception("PDF conversion failed")
    images[0].save(img_path, 'PNG')

    with open(img_path, "rb") as img:
        b64_image = base64.b64encode(img.read()).decode("utf-8")

    full_prompt = (
        "תייצר לי קובץ pdf שמכיל טבלה עם העמודות הבאות: איזור תוכנית, תיאור, כמות, יחידת מדידה,"
        " עלות משוערת מוצר, סה\"כ. תציג את המידע בטבלה לפי תוכנית העבודה בתמונה ששלחתי לך."
        " נא להתייחס לעמודה של הכמות לאחר חישוב ובהתאם לאופני המדידה הקיימים ובהתאם ליחידות המדידה הנהוגים."
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
    result_text = response.choices[0].message.content

    create_hebrew_table_pdf(output_pdf_path, result_text)

    os.remove(pdf_path)
    os.remove(img_path)

    return send_file(output_pdf_path, mimetype='application/pdf')


if __name__ == "__main__":
    app.run(port=5000)
