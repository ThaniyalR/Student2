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
        if self.path != "/api/chat":
            self._send_json(404, {"error": "Not found."})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._send_json(400, {"error": "Invalid request body."})
            return

        message = data.get("message", "")
        if not isinstance(message, str) or not message.strip():
            self._send_json(400, {"error": "Please type a question."})
            return

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            self._send_json(503, {
                "error": "Add GEMINI_API_KEY in Vercel Environment Variables."
            })
            return

        payload = json.dumps({
            "system_instruction": {
                "parts": [{"text": (
                    "You are SmartStudy AI, a friendly AI study tutor. "
                    "Help students understand academic and general questions. "
                    "Explain difficult topics simply, and give examples when useful."
                )}]
            },
            "contents": [{"parts": [{"text": message.strip()}]}]
        }).encode("utf-8")

        gemini_request = Request(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-3.8-flash:generateContent?key={api_key}",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urlopen(gemini_request, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))
            reply = result["candidates"][0]["content"]["parts"][0]["text"]
            self._send_json(200, {"reply": reply})
        except HTTPError as error:
            if error.code in {400, 401, 403}:
                self._send_json(401, {
                    "error": "GEMINI_API_KEY is invalid or lacks Gemini API access."
                })
            elif error.code == 429:
                self._send_json(429, {
                    "error": "The Gemini API free-tier limit was reached."
                })
            else:
                self._send_json(502, {
                    "error": "The Gemini request failed. Try again later."
                })
        except (URLError, KeyError, IndexError, json.JSONDecodeError):
            self._send_json(502, {
                "error": "The Gemini request failed. Try again later."
            })

    def do_GET(self):
        self._send_json(405, {"error": "Use POST for chat requests."})
