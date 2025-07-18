import os
import uuid
import base64
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


models = client.models.list()
for m in models.data:
    print(m.id)


@app.route("/")
def index():
    return jsonify(status="OK", message="Backend is alive")


@app.route('/api/convert', methods=['POST'])
def handle_pdf_to_vision():
    if 'pdf' not in request.files:
        return jsonify({'error': 'No PDF file provided'}), 400

    pdf_file = request.files['pdf']
    pdf_id = str(uuid.uuid4())
    pdf_path = os.path.join(UPLOAD_FOLDER, f"{pdf_id}.pdf")
    image_path = os.path.join(UPLOAD_FOLDER, f"{pdf_id}.png")

    try:
        # Save PDF to disk
        pdf_file.save(pdf_path)

        # Convert first page of PDF to image
        images = convert_from_path(pdf_path, dpi=100)
        if not images:
            raise Exception("PDF conversion returned no images.")
        images[0].save(image_path, 'PNG')

        # Read and encode image to base64
        with open(image_path, "rb") as img_file:
            base64_image = base64.b64encode(img_file.read()).decode("utf-8")

        # Call OpenAI GPT-4 Vision
        response = client.chat.completions.create(
            model="gpt-4o",  # ✅ this is your vision-enabled model
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "יש פה תוכנית עבודה, אני צריך שתוציא לי את כמויות החומרים עבור אומדן."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1500
        )

        # Extract text from response
        result_text = response.choices[0].message.content

        # Clean up temp files
        os.remove(pdf_path)
        os.remove(image_path)

        return jsonify({'result': result_text})

    except Exception as e:
        print("Error:", e)
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(port=5000)
