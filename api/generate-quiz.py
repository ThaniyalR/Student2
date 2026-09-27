import json
import os
from http.server import BaseHTTPRequestHandler
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class handler(BaseHTTPRequestHandler):
    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/api/generate-quiz":
            self._send_json(404, {"error": "Not found."})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._send_json(400, {"error": "Invalid request body."})
            return

        if not isinstance(data, dict):
            self._send_json(400, {"error": "Invalid request body."})
            return

        subject = data.get("subject", "Computer Science")
        difficulty = data.get("difficulty", "medium")
        if not isinstance(subject, str) or not isinstance(difficulty, str):
            self._send_json(400, {"error": "Invalid quiz settings."})
            return

        try:
            count = int(data.get("count", 10))
        except (TypeError, ValueError):
            count = 10
        count = max(1, min(count, 20))

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            self._send_json(503, {
                "error": "Add GEMINI_API_KEY in Vercel Environment Variables."
            })
            return

        prompt = f"""Create exactly {count} multiple-choice questions for a student.

Subject: {subject}
Difficulty: {difficulty}

Requirements:
- Each question must have exactly 4 options.
- Only one option must be correct.
- Make the questions educational and accurate.
- Do not include explanations.
- Return ONLY valid JSON in this format:
{{
  "questions": [
    {{
      "question": "Question text",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "answer": 0
    }}
  ]
}}

The answer must be the zero-based index of the correct option."""

        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 1.0,
                "responseMimeType": "application/json"
            }
        }).encode("utf-8")

        gemini_request = Request(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-3.8-flash:generateContent?key={api_key}",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urlopen(gemini_request, timeout=60) as response:
                result = json.loads(response.read().decode("utf-8"))

            quiz = json.loads(
                result["candidates"][0]["content"]["parts"][0]["text"]
            )
            questions = quiz["questions"]
            if len(questions) != count:
                raise ValueError("Wrong number of questions")

            for question in questions:
                if (
                    not isinstance(question.get("question"), str)
                    or not isinstance(question.get("options"), list)
                    or len(question["options"]) != 4
                    or question.get("answer") not in (0, 1, 2, 3)
                ):
                    raise ValueError("Invalid question format")

            self._send_json(200, quiz)
        except HTTPError as error:
            if error.code in {400, 401, 403}:
                self._send_json(401, {
                    "error": "Gemini API key is invalid or lacks API access."
                })
            elif error.code == 429:
                self._send_json(429, {
                    "error": "Gemini API limit reached. Try again later."
                })
            elif error.code == 503:
                self._send_json(503, {
                    "error": "Gemini is temporarily busy. Try again later."
                })
            else:
                self._send_json(502, {"error": "Quiz generation failed."})
        except (URLError, KeyError, IndexError, json.JSONDecodeError, ValueError):
            self._send_json(502, {
                "error": "Gemini could not generate a valid quiz. Try again."
            })