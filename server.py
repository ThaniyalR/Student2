from flask import Flask, request, jsonify, send_from_directory
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

@app.route("/")
def home():
    return send_from_directory(".", "student.html")


@app.route("/chat", methods=["POST"])
def chat():

    try:
        data = request.get_json()

        message = data.get("message", "").strip()

        if not message:
            return jsonify({
                "reply": "Please type a question."
            }), 400

        response = client.responses.create(
            model="gpt-5.6-luna",
            instructions="""
            You are SmartStudy AI, a friendly AI study tutor.

            Help students understand any academic or general question.
            Explain difficult topics in simple language.
            Give examples when useful.
            For programming questions, provide clear explanations and code.
            If the student asks a question unrelated to studying, answer it
            normally but keep the response helpful and concise.
            """,
            input=message
        )

        return jsonify({
            "reply": response.output_text
        })

    except Exception as e:

        print("ERROR:", e)

        return jsonify({
            "reply": "Sorry, I couldn't connect to the AI right now."
        }), 500


if __name__ == "__main__":
    app.run(debug=True)