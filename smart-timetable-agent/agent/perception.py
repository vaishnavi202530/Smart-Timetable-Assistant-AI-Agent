"""
perception.py
--------------
The agent's "senses". Converts raw natural-language input from the user
into a structured Intent the planner can reason over.

Two modes:
  1. Rule-based (default, no API key needed) - fast regex/keyword matching
     that covers the full command surface of this assistant.
  2. LLM-assisted (optional) - if ANTHROPIC_API_KEY is set in the
     environment, ambiguous free-text queries that don't match a rule
     are handed to Claude for intent extraction as JSON. This is what
     makes the agent "understand" phrasing the rules didn't anticipate.
"""

import os
import re
import json


KNOWN_INTENTS = {
    "GENERATE_TIMETABLE",
    "SHOW_SECTION_SCHEDULE",
    "SHOW_TEACHER_SCHEDULE",
    "FIND_FREE_SLOT",
    "CHECK_CONFLICTS",
    "RESCHEDULE_CLASS",
    "LIST_SECTIONS",
    "LIST_TEACHERS",
    "HELP",
    "UNKNOWN",
}


class Intent:
    def __init__(self, name, entities=None, raw_text=""):
        self.name = name
        self.entities = entities or {}
        self.raw_text = raw_text

    def __repr__(self):
        return f"Intent({self.name}, {self.entities})"


DAY_WORDS = r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"


def _extract_day(text):
    m = re.search(DAY_WORDS, text, re.IGNORECASE)
    return m.group(1).capitalize() if m else None


def _extract_period(text):
    m = re.search(r"period\s*(\d+)|p(\d+)", text, re.IGNORECASE)
    if m:
        return m.group(1) or m.group(2)
    return None


def _extract_section(text, known_sections):
    for sec in known_sections:
        if sec.lower() in text.lower():
            return sec
    return None


def _extract_teacher(text, teachers):
    for t in teachers:
        if t["id"].lower() in text.lower() or t["name"].lower() in text.lower():
            return t["id"]
        # match by surname
        surname = t["name"].split()[-1].lower()
        if surname in text.lower():
            return t["id"]
    return None


def _extract_course(text, sections):
    all_courses = set()
    for s in sections:
        for c in s["courses"]:
            all_courses.add(c["course"])
    for course in sorted(all_courses, key=len, reverse=True):
        if course.lower() in text.lower():
            return course
    return None


class RuleBasedParser:
    def __init__(self, sections, teachers):
        self.sections = sections
        self.teachers = teachers
        self.known_sections = [s["id"] for s in sections]

    def parse(self, text):
        t = text.strip().lower()

        if re.search(r"\b(generate|create|build|make)\b.*\btimetable\b", t):
            return Intent("GENERATE_TIMETABLE", raw_text=text)

        if re.search(r"\bhelp\b|\bwhat can you do\b|\bcommands\b", t):
            return Intent("HELP", raw_text=text)

        if re.search(r"\blist\b.*\bsections?\b|\bwhich sections\b", t):
            return Intent("LIST_SECTIONS", raw_text=text)

        if re.search(r"\blist\b.*\bteachers?\b|\bwhich teachers\b|\bfaculty list\b", t):
            return Intent("LIST_TEACHERS", raw_text=text)

        if re.search(r"\bconflicts?\b|\bclashes?\b", t):
            return Intent("CHECK_CONFLICTS", raw_text=text)

        if re.search(r"\breschedule\b|\bmove\b.*\bclass\b|\bshift\b", t):
            section = _extract_section(text, self.known_sections)
            course = _extract_course(text, self.sections)
            days = re.findall(DAY_WORDS, text, re.IGNORECASE)
            periods = re.findall(r"period\s*(\d+)|p(\d+)", text, re.IGNORECASE)
            from_day = days[0].capitalize() if len(days) >= 1 else None
            to_day = days[1].capitalize() if len(days) >= 2 else from_day
            flat_periods = [a or b for a, b in periods]
            from_period = flat_periods[0] if len(flat_periods) >= 1 else None
            to_period = flat_periods[1] if len(flat_periods) >= 2 else None
            return Intent(
                "RESCHEDULE_CLASS",
                entities={
                    "section": section,
                    "course": course,
                    "from_day": from_day,
                    "from_period": from_period,
                    "to_day": to_day,
                    "to_period": to_period,
                },
                raw_text=text,
            )

        if re.search(r"\bfree slot\b|\bavailable\b|\bwhen is\b.*\bfree\b", t):
            teacher = _extract_teacher(text, self.teachers)
            day = _extract_day(text)
            return Intent(
                "FIND_FREE_SLOT",
                entities={"teacher": teacher, "day": day},
                raw_text=text,
            )

        teacher = _extract_teacher(text, self.teachers)
        if teacher and re.search(r"\bschedule\b|\btimetable\b|\bclasses\b", t):
            return Intent("SHOW_TEACHER_SCHEDULE", entities={"teacher": teacher}, raw_text=text)

        section = _extract_section(text, self.known_sections)
        if section:
            return Intent("SHOW_SECTION_SCHEDULE", entities={"section": section}, raw_text=text)

        return Intent("UNKNOWN", raw_text=text)


class Perception:
    """Wraps the rule-based parser and (optionally) an LLM fallback."""

    def __init__(self, sections, teachers):
        self.rule_parser = RuleBasedParser(sections, teachers)
        self.sections = sections
        self.teachers = teachers
        self.llm_available = bool(os.environ.get("ANTHROPIC_API_KEY"))

    def understand(self, text):
        intent = self.rule_parser.parse(text)
        if intent.name != "UNKNOWN" or not self.llm_available:
            return intent
        return self._llm_fallback(text) or intent

    def _llm_fallback(self, text):
        """Optional: use Claude to interpret free-form phrasing the rules missed."""
        try:
            import anthropic
        except ImportError:
            return None

        section_ids = [s["id"] for s in self.sections]
        teacher_ids = [t["id"] for t in self.teachers]
        system = (
            "You convert a user's timetable request into strict JSON with keys "
            "'intent' (one of: GENERATE_TIMETABLE, SHOW_SECTION_SCHEDULE, "
            "SHOW_TEACHER_SCHEDULE, FIND_FREE_SLOT, CHECK_CONFLICTS, "
            "RESCHEDULE_CLASS, LIST_SECTIONS, LIST_TEACHERS, HELP, UNKNOWN) "
            f"and 'entities' (section from {section_ids}, teacher from {teacher_ids}, "
            "day, period, course, from_day, from_period, to_day, to_period as relevant). "
            "Reply with ONLY the JSON object, nothing else."
        )
        try:
            client = anthropic.Anthropic()
            resp = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=300,
                system=system,
                messages=[{"role": "user", "content": text}],
            )
            raw = "".join(b.text for b in resp.content if b.type == "text")
            raw = raw.strip().strip("`").replace("json\n", "")
            data = json.loads(raw)
            if data.get("intent") in KNOWN_INTENTS:
                return Intent(data["intent"], entities=data.get("entities", {}), raw_text=text)
        except Exception:
            return None
        return None
