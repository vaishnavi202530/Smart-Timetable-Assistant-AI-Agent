"""
scheduler.py
------------
The constraint-solving core of the Smart Timetable Assistant.

This treats timetable generation as a Constraint Satisfaction Problem (CSP):
  - Variables : one per (section, course, session_number)
  - Domain    : every (day, period, room) slot
  - Constraints:
        1. A section cannot have two classes at the same (day, period)
        2. A teacher cannot teach two classes at the same (day, period)
        3. A room cannot host two classes at the same (day, period)
        4. Lab sessions must be assigned to a room of type 'lab'
        5. Lecture sessions must be assigned to a room of type 'classroom'
        6. A teacher should not exceed max_periods_per_day_per_teacher

The solver uses randomized backtracking with a "most constrained first"
ordering and several retries, which in practice finds a clash-free
timetable very quickly for realistic institutional data.
"""

import json
import random
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class Session:
    """One weekly occurrence of a course that needs a slot assigned."""

    __slots__ = ("section", "course", "teacher", "room_type", "index")

    def __init__(self, section, course, teacher, room_type, index):
        self.section = section
        self.course = course
        self.teacher = teacher
        self.room_type = room_type
        self.index = index

    def __repr__(self):
        return f"<Session {self.section}/{self.course}#{self.index}>"


class TimetableEngine:
    def __init__(self, data_dir=DATA_DIR):
        self.data_dir = Path(data_dir)
        self.config = self._load("config.json")
        self.teachers = {t["id"]: t for t in self._load("teachers.json")}
        self.rooms = self._load("rooms.json")
        self.sections = self._load("sections.json")

        self.days = self.config["days"]
        self.periods = [p["index"] for p in self.config["periods"]]
        self.max_periods_per_teacher = self.config.get(
            "max_periods_per_day_per_teacher", 6
        )

        # timetable[day][period] -> list of assignment dicts
        self.timetable = defaultdict(lambda: defaultdict(list))
        self.unplaced = []  # sessions that could not be placed

    def _load(self, filename):
        with open(self.data_dir / filename, "r") as f:
            return json.load(f)

    # ------------------------------------------------------------------
    # Building the list of CSP variables (sessions) from section data
    # ------------------------------------------------------------------
    def _build_sessions(self):
        sessions = []
        for section in self.sections:
            for course in section["courses"]:
                room_type = "lab" if course["type"] == "lab" else "classroom"
                for i in range(course["sessions_per_week"]):
                    sessions.append(
                        Session(
                            section=section["id"],
                            course=course["course"],
                            teacher=course["teacher"],
                            room_type=room_type,
                            index=i + 1,
                        )
                    )
        return sessions

    # ------------------------------------------------------------------
    # Core solver
    # ------------------------------------------------------------------
    def generate(self, max_attempts=60, seed=None):
        """Try several randomized backtracking passes and keep the best."""
        rng = random.Random(seed)
        best_result = None
        best_unplaced = None

        for attempt in range(max_attempts):
            sessions = self._build_sessions()
            rng.shuffle(sessions)
            # Most-constrained-first: courses with fewer valid room options go first
            sessions.sort(key=lambda s: 0 if s.room_type == "lab" else 1)

            grid = defaultdict(lambda: defaultdict(list))
            section_busy = defaultdict(set)   # (section) -> {(day,period)}
            teacher_busy = defaultdict(set)   # (teacher) -> {(day,period)}
            room_busy = defaultdict(set)       # (room) -> {(day,period)}
            teacher_daily_count = defaultdict(lambda: defaultdict(int))

            unplaced = []
            slots = [(d, p) for d in self.days for p in self.periods]

            for session in sessions:
                candidate_rooms = [
                    r["id"] for r in self.rooms if r["type"] == session.room_type
                ]
                rng.shuffle(slots)
                placed = False

                for day, period in slots:
                    if (day, period) in section_busy[session.section]:
                        continue
                    if (day, period) in teacher_busy[session.teacher]:
                        continue
                    if teacher_daily_count[session.teacher][day] >= self.max_periods_per_teacher:
                        continue

                    rng.shuffle(candidate_rooms)
                    for room in candidate_rooms:
                        if (day, period) in room_busy[room]:
                            continue
                        # place it
                        grid[day][period].append(
                            {
                                "section": session.section,
                                "course": session.course,
                                "teacher": session.teacher,
                                "teacher_name": self.teachers[session.teacher]["name"],
                                "room": room,
                            }
                        )
                        section_busy[session.section].add((day, period))
                        teacher_busy[session.teacher].add((day, period))
                        room_busy[room].add((day, period))
                        teacher_daily_count[session.teacher][day] += 1
                        placed = True
                        break
                    if placed:
                        break

                if not placed:
                    unplaced.append(session)

            if best_unplaced is None or len(unplaced) < best_unplaced:
                best_result = grid
                best_unplaced = len(unplaced)
                self.unplaced = unplaced

            if best_unplaced == 0:
                break

        self.timetable = best_result
        return {
            "success": best_unplaced == 0,
            "unplaced_count": best_unplaced,
            "unplaced": [repr(s) for s in self.unplaced],
        }

    # ------------------------------------------------------------------
    # Query helpers used by the agent's tools
    # ------------------------------------------------------------------
    def schedule_for_section(self, section_id):
        result = {day: {} for day in self.days}
        for day in self.days:
            for period in self.periods:
                for entry in self.timetable.get(day, {}).get(period, []):
                    if entry["section"] == section_id:
                        result[day][period] = entry
        return result

    def schedule_for_teacher(self, teacher_id):
        result = {day: {} for day in self.days}
        for day in self.days:
            for period in self.periods:
                for entry in self.timetable.get(day, {}).get(period, []):
                    if entry["teacher"] == teacher_id:
                        result[day][period] = entry
        return result

    def free_slots_for_teacher(self, teacher_id):
        busy = set()
        for day in self.days:
            for period in self.periods:
                for entry in self.timetable.get(day, {}).get(period, []):
                    if entry["teacher"] == teacher_id:
                        busy.add((day, period))
        return [(d, p) for d in self.days for p in self.periods if (d, p) not in busy]

    def free_rooms_at(self, day, period, room_type=None):
        busy_rooms = {
            e["room"] for e in self.timetable.get(day, {}).get(period, [])
        }
        candidates = [r for r in self.rooms if room_type in (None, r["type"])]
        return [r["id"] for r in candidates if r["id"] not in busy_rooms]

    def find_conflicts(self):
        """Sanity check the generated grid for any double-bookings."""
        conflicts = []
        for day in self.days:
            for period in self.periods:
                entries = self.timetable.get(day, {}).get(period, [])
                seen_sections, seen_teachers, seen_rooms = {}, {}, {}
                for e in entries:
                    for key, store, label in (
                        (e["section"], seen_sections, "section"),
                        (e["teacher"], seen_teachers, "teacher"),
                        (e["room"], seen_rooms, "room"),
                    ):
                        if key in store:
                            conflicts.append(
                                f"{label} clash on {day} P{period}: "
                                f"{store[key]['course']} vs {e['course']}"
                            )
                        else:
                            store[key] = e
        return conflicts

    def move_session(self, section_id, course_name, from_day, from_period, to_day, to_period):
        """Reschedule one class, validating the new slot is free."""
        from_period, to_period = int(from_period), int(to_period)
        entries = self.timetable.get(from_day, {}).get(from_period, [])
        target = next(
            (e for e in entries if e["section"] == section_id and e["course"].lower() == course_name.lower()),
            None,
        )
        if not target:
            return {"success": False, "reason": "No such class found at that slot."}

        # check destination free for section, teacher, room
        dest_entries = self.timetable.get(to_day, {}).get(to_period, [])
        for e in dest_entries:
            if e["section"] == section_id:
                return {"success": False, "reason": f"{section_id} already has a class then."}
            if e["teacher"] == target["teacher"]:
                return {"success": False, "reason": f"{target['teacher_name']} is already teaching then."}
            if e["room"] == target["room"]:
                return {"success": False, "reason": f"Room {target['room']} is already booked then."}

        entries.remove(target)
        self.timetable[to_day][to_period].append(target)
        return {"success": True, "moved": target, "to": (to_day, to_period)}
