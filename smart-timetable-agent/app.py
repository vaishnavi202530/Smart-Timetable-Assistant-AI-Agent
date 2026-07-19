#!/usr/bin/env python3
"""
app.py
------
Flask front-end for the Smart Timetable Assistant AI Agent.

Run:
    python3 app.py
Then open:
    http://127.0.0.1:5000
"""

from flask import Flask, request, jsonify, render_template

from agent import TimetableAgent

app = Flask(__name__, template_folder="web/templates", static_folder="web/static")

# One shared agent instance holds the "world state" (generated timetable,
# conversation memory) for this running server - simplest possible setup
# for a demo / single-institution deployment.
agent = TimetableAgent()


@app.route("/")
def index():
    return render_template(
        "index.html",
        sections=[s["id"] for s in agent.engine.sections],
        teachers=list(agent.engine.teachers.values()),
    )


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    message = (data or {}).get("message", "").strip()
    if not message:
        return jsonify({"response": "Say something and I'll help with the timetable."})
    result = agent.handle_message(message)
    return jsonify(result)


@app.route("/api/timetable")
def timetable():
    return jsonify(agent.full_timetable_json())


@app.route("/api/config")
def config():
    return jsonify(agent.engine.config)


if __name__ == "__main__":
    print("Smart Timetable Assistant running at http://127.0.0.1:5000")
    app.run(debug=True, port=5000)
