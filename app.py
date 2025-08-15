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
def pdf_to_images(pdf_bytes: bytes, dpi: int = 150):
    """Convert PDF bytes to a list of PIL images, one per page."""
    images = convert_from_bytes(pdf_bytes, dpi=dpi)
    if not images:
        raise ValueError("PDF conversion returned no images.")
    return images


def split_image_into_tiles(image: Image.Image, max_tile_size: int = 2000):
    """
    Splits a large image into smaller tiles (max_tile_size x max_tile_size) to reduce memory usage.
    Returns a list of PIL Image tiles.
    """
    tiles = []
    w, h = image.size
    for top in range(0, h, max_tile_size):
        for left in range(0, w, max_tile_size):
            right = min(left + max_tile_size, w)
            bottom = min(top + max_tile_size, h)
            tile = image.crop((left, top, right, bottom))
            tiles.append(tile)
    return tiles


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


def pdf_to_base64_tiles(pdf_bytes: bytes, dpi: int = 150, img_format: str = "PNG", quality: int = 95, max_tile_size: int = 2000):
    """
    Converts a PDF to base64 images, splitting large pages into smaller tiles.
    Returns a list of base64 images.
    """
    pil_images = pdf_to_images(pdf_bytes, dpi=dpi)
    base64_images = []

    for page_idx, img in enumerate(pil_images):
        # Resize very large pages to avoid extreme memory usage
        max_dim = 4000
        if img.width > max_dim or img.height > max_dim:
            ratio = min(max_dim / img.width, max_dim / img.height)
            img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)

        # Split large pages into tiles
        tiles = split_image_into_tiles(img, max_tile_size=max_tile_size)
        for tile_idx, tile in enumerate(tiles):
            base64_images.append(image_to_base64(tile, img_format=img_format, quality=quality))

    return base64_images


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
        base64_tiles = pdf_to_base64_tiles(pdf_bytes, dpi=150, max_tile_size=2000)

        results = []
        for idx, b64_img in enumerate(base64_tiles):
            prompt_text = free_text if free_text else f"Please read blueprint tile {idx+1} and extract quantities."

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
                max_completion_tokens=3000
            )
            results.append(response.choices[0].message.content)

        return jsonify({"tiles": results})

    except Exception as e:
        print("Error:", e)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(port=5000)
