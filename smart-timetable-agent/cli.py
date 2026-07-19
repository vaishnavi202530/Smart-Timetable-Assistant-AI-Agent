#!/usr/bin/env python3
"""
cli.py
------
Zero-dependency way to run the Smart Timetable Assistant AI Agent in a
terminal chat loop. Great for a quick demo without starting the web server.

Usage:
    python3 cli.py
"""

from agent import TimetableAgent


BANNER = r"""
============================================================
   SMART TIMETABLE ASSISTANT AI AGENT   (CLI mode)
============================================================
Type 'help' to see what I can do, or 'exit' to quit.
Tip: start with -> generate the timetable
"""


def main():
    print(BANNER)
    agent = TimetableAgent()

    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not text:
            continue
        if text.lower() in {"exit", "quit", "bye"}:
            print("agent> Goodbye! Have a well-scheduled day.")
            break

        result = agent.handle_message(text)
        print(f"agent> {result['response']}\n")


if __name__ == "__main__":
    main()
