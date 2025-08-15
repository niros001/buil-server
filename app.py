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

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ------------------ PDF TO IMAGE UTILITIES ------------------ #
def pdf_to_images(pdf_bytes: bytes, dpi: int = 200):
    """Convert PDF bytes to a list of PIL images."""
    images = convert_from_bytes(pdf_bytes, dpi=dpi)
    if not images:
        raise ValueError("PDF conversion returned no images.")
    return images


def image_to_base64(image: Image.Image, img_format: str = "PNG", quality: int = 95) -> str:
    """Convert a PIL Image to a base64 string."""
    img_buffer = io.BytesIO()
    img_format_upper = img_format.upper()
    if img_format_upper == "JPEG":
        quality = max(1, min(quality, 95))
        image.save(img_buffer, format="JPEG", quality=quality)
    else:
        image.save(img_buffer, format="PNG")
    img_buffer.seek(0)
    return base64.b64encode(img_buffer.read()).decode("utf-8")


def pdf_to_base64_images(pdf_bytes: bytes, dpi: int = 200, img_format: str = "PNG", quality: int = 95):
    """
    Convert each page of a PDF into a base64-encoded image string.
    Handles large pages safely by resizing if needed.
    """
    pil_images = pdf_to_images(pdf_bytes, dpi=dpi)
    base64_pages = []

    for idx, img in enumerate(pil_images):
        # Resize very large images to prevent out-of-memory errors
        max_dim = 4000  # max width or height
        if img.width > max_dim or img.height > max_dim:
            ratio = min(max_dim / img.width, max_dim / img.height)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)

        base64_pages.append(image_to_base64(img, img_format=img_format, quality=quality))

    return base64_pages


# ------------------ FLASK ROUTES ------------------ #
@app.route("/")
def index():
    return jsonify(status="OK", message="Backend is alive")


@app.route("/api/convert", methods=["POST"])
def handle_pdf_to_gpt5():
    if "pdf" not in request.files:
        return jsonify({"error": "No PDF file provided"}), 400

    pdf_file = request.files["pdf"]
    free_text = request.form.get("free_text", "")
    try:
        pdf_bytes = pdf_file.read()
        base64_pages = pdf_to_base64_images(pdf_bytes, dpi=200)

        # Prepare GPT-5 Vision requests for all pages
        results = []
        for idx, b64_img in enumerate(base64_pages):
            prompt_text = free_text if free_text else f"Please read the blueprint on page {idx+1} and summarize quantities."

            response = client.chat.completions.create(
                model="gpt-5",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt_text},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}"}}
                        ]
                    }
                ],
                max_completion_tokens=3000  # recommended for large outputs
            )
            results.append(response.choices[0].message.content)

        return jsonify({"pages": results})

    except Exception as e:
        print("Error:", e)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(port=5000)
