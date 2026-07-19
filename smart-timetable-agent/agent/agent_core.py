"""
agent_core.py
-------------
The TimetableAgent class implements the classic agentic loop:

        ┌────────┐     ┌────────┐     ┌────────┐
  text →│ SENSE  │────▶│ THINK  │────▶│  ACT   │──▶ response
        │(percep-│     │(planner│     │ (tools │
        │  tion) │     │ picks a│     │  run   │
        └────────┘     │  tool) │     │ against│
                        └────────┘     │ engine)│
                                        └────────┘
                              ▲              │
                              └── memory ────┘
                          (context carried across turns)

This is deliberately framework-free so the whole decision loop is
visible and auditable in one file - useful for a viva/demo where you
need to explain exactly how the agent decides what to do.
"""

from .scheduler import TimetableEngine
from .perception import Perception
from .memory import Memory
from . import tools


class TimetableAgent:
    def __init__(self):
        self.engine = TimetableEngine()
        self.perception = Perception(self.engine.sections, list(self.engine.teachers.values()))
        self.memory = Memory()

    # ------------------------------------------------------------------
    def handle_message(self, text):
        """One full agentic cycle: sense -> think -> act -> remember."""
        self.memory.log("user", text)

        intent = self.perception.understand(text)
        intent = self._resolve_with_context(intent)

        response = self._act(intent)

        self.memory.remember_intent(intent)
        self.memory.log("agent", response)
        return {
            "response": response,
            "intent": intent.name,
            "entities": intent.entities,
        }

    # ------------------------------------------------------------------
    def _resolve_with_context(self, intent):
        """Fill in missing entities from the previous turn (basic coreference)."""
        if intent.name == "RESCHEDULE_CLASS":
            if not intent.entities.get("section") and self.memory.last_entities:
                intent.entities["section"] = self.memory.recall_entity("section")
            if not intent.entities.get("course") and self.memory.last_entities:
                intent.entities["course"] = self.memory.recall_entity("course")
        return intent

    # ------------------------------------------------------------------
    def _act(self, intent):
        engine = self.engine
        e = intent.entities

        dispatch = {
            "GENERATE_TIMETABLE": lambda: tools.tool_generate_timetable(engine),
            "SHOW_SECTION_SCHEDULE": lambda: tools.tool_show_section_schedule(
                engine, e.get("section")
            ),
            "SHOW_TEACHER_SCHEDULE": lambda: tools.tool_show_teacher_schedule(
                engine, e.get("teacher")
            ),
            "FIND_FREE_SLOT": lambda: tools.tool_find_free_slot(
                engine, e.get("teacher"), e.get("day")
            ),
            "CHECK_CONFLICTS": lambda: tools.tool_check_conflicts(engine),
            "RESCHEDULE_CLASS": lambda: tools.tool_reschedule_class(
                engine,
                e.get("section"),
                e.get("course"),
                e.get("from_day"),
                e.get("from_period"),
                e.get("to_day"),
                e.get("to_period"),
            ),
            "LIST_SECTIONS": lambda: tools.tool_list_sections(engine),
            "LIST_TEACHERS": lambda: tools.tool_list_teachers(engine),
            "HELP": lambda: tools.tool_help(),
            "UNKNOWN": lambda: (
                "I didn't quite catch that. Type 'help' to see what I can do."
            ),
        }

        handler = dispatch.get(intent.name, dispatch["UNKNOWN"])
        try:
            return handler()
        except Exception as exc:  # keep the agent alive even if a tool errors
            return f"Something went wrong handling that request: {exc}"

    # ------------------------------------------------------------------
    def full_timetable_json(self):
        """Used by the web UI to render the grid view."""
        engine = self.engine
        grid = {day: {p: [] for p in engine.periods} for day in engine.days}
        for day in engine.days:
            for period in engine.periods:
                for entry in engine.timetable.get(day, {}).get(period, []):
                    grid[day][period].append(entry)
        return {
            "days": engine.days,
            "periods": engine.periods,
            "grid": grid,
            "sections": [s["id"] for s in engine.sections],
        }
