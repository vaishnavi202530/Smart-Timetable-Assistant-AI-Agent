"""
tools.py
--------
The agent's "hands". Each function is a discrete tool the planner can
invoke. Keeping these separate from the planner/perception means new
capabilities can be added without touching the NLU layer.
"""


def tool_generate_timetable(engine):
    result = engine.generate(max_attempts=80)
    if result["success"]:
        return "Timetable generated successfully with zero clashes across all sections."
    return (
        f"Timetable generated with {result['unplaced_count']} session(s) that could not "
        "be placed without a clash. Consider adding another room or relaxing a constraint."
    )


def tool_show_section_schedule(engine, section_id):
    if not any(s["id"] == section_id for s in engine.sections):
        return f"I don't recognize section '{section_id}'. Try: " + ", ".join(
            s["id"] for s in engine.sections
        )
    schedule = engine.schedule_for_section(section_id)
    return _format_schedule(engine, schedule, title=f"Schedule for {section_id}")


def tool_show_teacher_schedule(engine, teacher_id):
    if teacher_id not in engine.teachers:
        return "I couldn't identify that teacher. Try asking 'list teachers'."
    schedule = engine.schedule_for_teacher(teacher_id)
    name = engine.teachers[teacher_id]["name"]
    return _format_schedule(engine, schedule, title=f"Schedule for {name}", show_section=True)


def tool_find_free_slot(engine, teacher_id, day=None):
    if not teacher_id:
        return "Tell me which teacher, e.g. 'find free slot for Dr. Sharma on Monday'."
    if teacher_id not in engine.teachers:
        return "I couldn't identify that teacher."
    free = engine.free_slots_for_teacher(teacher_id)
    if day:
        free = [f for f in free if f[0] == day]
    name = engine.teachers[teacher_id]["name"]
    if not free:
        return f"{name} has no free periods{' on ' + day if day else ''}."
    lines = [f"Free slots for {name}{' on ' + day if day else ''}:"]
    for d, p in free[:15]:
        lines.append(f"  - {d}, Period {p}")
    if len(free) > 15:
        lines.append(f"  ...and {len(free) - 15} more.")
    return "\n".join(lines)


def tool_check_conflicts(engine):
    conflicts = engine.find_conflicts()
    if not conflicts:
        return "No conflicts found. The timetable is fully clash-free."
    return "Found the following conflicts:\n" + "\n".join(f"  - {c}" for c in conflicts)


def tool_reschedule_class(engine, section, course, from_day, from_period, to_day, to_period):
    missing = [
        name
        for name, val in [
            ("section", section),
            ("course", course),
            ("from_day", from_day),
            ("from_period", from_period),
            ("to_day", to_day),
            ("to_period", to_period),
        ]
        if not val
    ]
    if missing:
        return (
            "I need more details to reschedule: missing " + ", ".join(missing) + ". "
            "Example: 'reschedule Data Structures for CSE-A from Monday period 2 to "
            "Wednesday period 5'."
        )
    result = engine.move_session(section, course, from_day, from_period, to_day, to_period)
    if result["success"]:
        return (
            f"Done. {course} for {section} moved from {from_day} P{from_period} "
            f"to {to_day} P{to_period}."
        )
    return f"Couldn't reschedule: {result['reason']}"


def tool_list_sections(engine):
    lines = ["Sections:"]
    for s in engine.sections:
        courses = ", ".join(c["course"] for c in s["courses"])
        lines.append(f"  - {s['id']} ({s['strength']} students): {courses}")
    return "\n".join(lines)


def tool_list_teachers(engine):
    lines = ["Teachers:"]
    for t in engine.teachers.values():
        lines.append(f"  - {t['id']}: {t['name']} — {', '.join(t['subjects'])}")
    return "\n".join(lines)


def tool_help():
    return (
        "I'm your Smart Timetable Assistant. Try things like:\n"
        "  - generate the timetable\n"
        "  - show schedule for CSE-A\n"
        "  - show schedule for Dr. Sharma\n"
        "  - find free slot for Prof. Iyer on Tuesday\n"
        "  - check conflicts\n"
        "  - reschedule Data Structures for CSE-A from Monday period 2 to "
        "Wednesday period 5\n"
        "  - list sections / list teachers"
    )


# ----------------------------------------------------------------------
def _format_schedule(engine, schedule, title, show_section=False):
    lines = [title, "=" * len(title)]
    any_class = False
    for day in engine.days:
        day_entries = schedule.get(day, {})
        if not day_entries:
            continue
        any_class = True
        lines.append(f"\n{day}:")
        for period in sorted(day_entries):
            e = day_entries[period]
            label = f"{e['course']} ({e['room']})"
            if show_section:
                label = f"{e['section']} - {label}"
            else:
                label += f" — {e['teacher_name']}"
            lines.append(f"  P{period}: {label}")
    if not any_class:
        lines.append("\nNo classes scheduled yet. Try 'generate the timetable' first.")
    return "\n".join(lines)
