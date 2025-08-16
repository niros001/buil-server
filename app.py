import os
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv

# טוען משתני סביבה
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


@app.route('/api/convert', methods=['POST'])
def handle_pdf_to_ai():
    if 'pdf' not in request.files:
        return jsonify({'error': 'No PDF file provided'}), 400

    pdf_file = request.files['pdf']
    main_option = request.form.get('main_option')
    free_text = request.form.get('free_text', '')

    # ברירת מחדל אם המשתמש לא כתב שאלה
    user_prompt = free_text if main_option == 'custom' else \
        "קרא את התוכנית ופרט כמויות חומרים (ברזל, בטון, עץ)."

    try:
        # שומר זמנית את ה-PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            pdf_path = tmp.name
            pdf_file.save(pdf_path)

        # מעלה את הקובץ ל-OpenAI
        uploaded_file = client.files.create(
            file=open(pdf_path, "rb"),
            purpose="assistants"
        )

        # יוצר Assistant (רק בפעם הראשונה, אפשר לשמור assistant_id לשימוש חוזר)
        assistant = client.beta.assistants.create(
            name="Construction Plan Analyzer",
            model="gpt-4o",
            tools=[{"type": "file_search"}]
        )

        # יוצר Thread עם ההודעה + מצרף את הקובץ
        thread = client.beta.threads.create(
            messages=[
                {
                    "role": "user",
                    "content": user_prompt,
                    "attachments": [
                        {"file_id": uploaded_file.id, "tools": [{"type": "file_search"}]}
                    ]
                }
            ]
        )

        # מריץ את ה-Assistant על ה-Thread
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread.id,
            assistant_id=assistant.id
        )

        # קורא את התשובה
        messages = list(client.beta.threads.messages.list(thread_id=thread.id))
        answer = messages[0].content[0].text.value if messages else "אין תשובה"

        os.remove(pdf_path)  # מנקה את הקובץ הזמני

        return jsonify({'result': answer})

    except Exception as e:
        print("Error:", e)
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(port=5000)
