from pathlib import Path

from flask import Flask, abort, jsonify, request, send_from_directory
from openai import AuthenticationError, OpenAI, RateLimitError
from dotenv import load_dotenv
import os

PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env", override=True)

app = Flask(__name__)

@app.get("/")
def home():
    return send_from_directory(PROJECT_DIR, "index.html")


@app.get("/<path:filename>")
def project_file(filename):
    if Path(filename).suffix.lower() not in {".html", ".css", ".js"}:
        abort(404)
    return send_from_directory(PROJECT_DIR, filename)


@app.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "")
    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "Please type a question."}), 400

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return jsonify({
            "error": "Add OPENAI_API_KEY to a .env file in the project folder, then restart the server."
        }), 503

    try:
        response = OpenAI(api_key=api_key).responses.create(
            model="gpt-4o-mini",
            instructions="""
            You are SmartStudy AI, a friendly AI study tutor.

            Help students understand any academic or general question.
            Explain difficult topics in simple language.
            Give examples when useful.
            For programming questions, provide clear explanations and code.
            If the student asks a question unrelated to studying, answer it
            normally but keep the response helpful and concise.
            """,
            input=message.strip()
        )

        return jsonify({"reply": response.output_text})
    except AuthenticationError:
        return jsonify({
            "error": "OPENAI_API_KEY is invalid. Replace it in the project .env file, then restart the server."
        }), 401
    except RateLimitError as error:
        if getattr(error, "code", None) == "credit_balance_exhausted":
            return jsonify({
                "error": "OpenAI API credits are exhausted. Add billing or credits in your OpenAI Platform account."
            }), 429
        return jsonify({
            "error": "The OpenAI API rate limit was reached. Wait a moment and try again."
        }), 429
    except Exception as error:
        app.logger.error("AI chat request failed (%s)", type(error).__name__)
        return jsonify({
            "error": "The AI request failed. Check the server log and API access."
        }), 502


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)