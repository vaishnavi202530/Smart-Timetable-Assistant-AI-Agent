# Smart Timetable Assistant AI Agent

An **agentic AI** system that generates clash-free academic timetables and
lets you manage them through natural-language chat — "generate the
timetable", "show schedule for CSE-A", "find a free slot for Dr. Sharma",
"reschedule Data Structures for CSE-A from Monday period 2 to Wednesday
period 5", and so on.

It runs **fully offline with zero API keys** (rule-based NLU + a
constraint-solving scheduler), with an *optional* upgrade path to use
Claude for free-form language understanding.

---

## 1. Why this is "agentic" (not just a script)

The system implements the classic agent loop, explicitly, in code you can
read end to end:

```
User text
   │
   ▼
┌─────────────┐   SENSE: turn free text into a structured Intent
│ perception  │   (rule-based regex parser, optional Claude fallback)
└─────┬───────┘
      ▼
┌─────────────┐   THINK: decide which tool to call given the intent
│ agent_core  │   + memory (context/coreference across turns)
└─────┬───────┘
      ▼
┌─────────────┐   ACT: execute the tool against the world model
│   tools     │   (generate / query / reschedule / list …)
└─────┬───────┘
      ▼
┌─────────────┐   The "world" — a CSP-based timetable engine
│  scheduler  │   (sections, teachers, rooms, hard constraints)
└─────────────┘
      │
      ▼
 Natural-language response back to the user
```

- **Autonomy**: given a goal ("generate the timetable"), the agent runs a
  randomized backtracking search over ~60 attempts on its own, picking the
  best clash-free arrangement — you don't hand-place a single class.
- **Tool use**: the agent has a fixed toolbox (`agent/tools.py`) and picks
  the right tool per turn instead of one giant hardcoded script.
- **Memory**: `agent/memory.py` carries context between turns (e.g. a
  follow-up reschedule request can reuse the section/course just discussed).
- **Extensible reasoning**: if `ANTHROPIC_API_KEY` is set, phrasing that the
  rule-based parser doesn't recognize is handed to Claude to extract intent
  as JSON — the rest of the pipeline (tools, scheduler) is unchanged.

## 2. What actually solves the timetable

`agent/scheduler.py` models timetabling as a **Constraint Satisfaction
Problem**:

- **Variables**: one per (section, course, weekly session number)
- **Domain**: every (day, period, room) slot
- **Hard constraints**: no section/teacher/room double-booked; lab
  sessions only in lab rooms; a teacher's daily period cap is respected
- It performs randomized backtracking across multiple attempts and keeps
  the best (fewest unplaced) result — in practice it finds a 100%
  clash-free timetable for the sample data almost immediately.

All data (sections, courses, teachers, rooms, period timings) lives in
plain JSON under `data/`, so you can adapt it to your own institution
without touching any code.

## 3. Project structure

```
smart-timetable-agent/
├── agent/
│   ├── scheduler.py     # CSP engine: builds & queries the timetable
│   ├── perception.py    # NLU: text -> Intent (rules + optional Claude)
│   ├── memory.py        # conversation/context memory
│   ├── tools.py         # the agent's actions
│   └── agent_core.py    # the sense -> think -> act loop
├── data/
│   ├── config.json      # days, periods, breaks, constraints
│   ├── teachers.json
│   ├── rooms.json
│   └── sections.json    # sections + their weekly course load
├── web/
│   └── templates/index.html   # chat UI + live timetable grid
├── app.py               # Flask web server
├── cli.py               # terminal chat mode (no Flask needed)
├── requirements.txt
└── README.md
```

## 4. Running it

### Option A — Web app (recommended, has the visual grid)

```bash
cd smart-timetable-agent
pip install -r requirements.txt
python3 app.py
```

Open **http://127.0.0.1:5000** — click **Generate timetable**, then chat
with the agent on the right and watch the grid update on the left.

### Option B — Terminal chat only

```bash
cd smart-timetable-agent
python3 cli.py
```

No Flask required — just the Python standard library.

### Optional — enable the Claude fallback for free-form phrasing

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...      # your key
python3 app.py
```

Without this, the rule-based parser already covers every command listed
below — the Claude fallback only helps with phrasing the rules don't
recognize.

## 5. Example commands to try

```
generate the timetable
show schedule for CSE-A
show schedule for Dr. Sharma
find free slot for Prof. Iyer on Tuesday
check conflicts
reschedule Data Structures for CSE-A from Monday period 2 to Wednesday period 5
list sections
list teachers
help
```

## 6. Adapting it to your own college/department

1. Edit `data/sections.json` — list your sections and each one's weekly
   course load, assigned teacher, and session count.
2. Edit `data/teachers.json` and `data/rooms.json` to match your faculty
   and room inventory.
3. Edit `data/config.json` for your actual day/period timings.
4. Run `python3 app.py` and click **Generate timetable** — no code
   changes needed.

## 7. Extending the agent

Because perception, planning, tools, and the scheduler are separate
modules, adding a new capability is a 3-step pattern:

1. Add a new intent pattern in `agent/perception.py`
2. Add the corresponding function in `agent/tools.py`
3. Wire the intent name to that function in the `dispatch` dict inside
   `agent/agent_core.py`

For example, "swap two classes", "add a new course", or "email the
teacher their weekly schedule" can all be added this way without
touching the scheduler or the UI.
