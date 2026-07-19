"""
memory.py
---------
Simple working memory + conversation log for the agent.
Keeps the agent's loop stateful across turns (e.g. "reschedule it to
Friday instead" referring to the class just discussed).
"""

from datetime import datetime


class Memory:
    def __init__(self, max_history=50):
        self.history = []          # list of {role, text, timestamp}
        self.last_intent = None
        self.last_entities = {}
        self.max_history = max_history
        self.timetable_generated = False

    def log(self, role, text):
        self.history.append(
            {"role": role, "text": text, "timestamp": datetime.now().isoformat()}
        )
        self.history = self.history[-self.max_history:]

    def remember_intent(self, intent):
        self.last_intent = intent.name
        self.last_entities = intent.entities

    def recall_entity(self, key):
        return self.last_entities.get(key)

    def as_transcript(self):
        return "\n".join(f"{h['role']}: {h['text']}" for h in self.history)
