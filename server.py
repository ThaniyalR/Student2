from pathlib import Path
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Flask, abort, jsonify, request, send_from_directory
from dotenv import load_dotenv

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
@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "")
    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "Please type a question."}), 400

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return jsonify({
            "error": "Add GEMINI_API_KEY to a .env file in the project folder, then restart the server."
        }), 503

    try:
        payload = json.dumps({
            "system_instruction": {
                "parts": [{"text": (
                    "You are SmartStudy AI, a friendly AI study tutor. "
                    "Help students understand academic and general questions. "
                    "Explain difficult topics simply, and give examples when useful."
                )}]
            },
            "contents": [{
                "parts": [{"text": message.strip()}]
            }]
        }).encode("utf-8")
        gemini_request = Request(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-3.8-flash:generateContent?key={api_key}",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urlopen(gemini_request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))

        reply = result["candidates"][0]["content"]["parts"][0]["text"]
        return jsonify({"reply": reply})
    except HTTPError as error:
        if error.code in {400, 401, 403}:
            return jsonify({
                "error": "GEMINI_API_KEY is invalid or does not have Gemini API access."
            }), 401
        if error.code == 429:
            return jsonify({
                "error": "The Gemini API free-tier limit was reached. Try again later."
            }), 429
        if error.code == 503:
            return jsonify({
                "error": "Gemini is temporarily busy. Wait a few seconds and try again."
            }), 503
        app.logger.error("Gemini request failed with HTTP %s", error.code)
        return jsonify({"error": "The AI request failed. Check the server log."}), 502
    except (KeyError, IndexError, json.JSONDecodeError):
        app.logger.error("Gemini returned an unexpected response")
        return jsonify({"error": "The AI returned an unexpected response."}), 502
    except URLError:
        return jsonify({"error": "Could not connect to the Gemini API."}), 502
    except Exception as error:
        app.logger.error("AI chat request failed (%s)", type(error).__name__)
        return jsonify({
            "error": "The AI request failed. Check the server log and API access."
        }), 502


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)