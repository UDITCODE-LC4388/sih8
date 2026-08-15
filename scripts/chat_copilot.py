#!/usr/bin/env python3
"""
CLI Interactive Lunar Mission Copilot Chatbot

Usage:
  python scripts/chat_copilot.py
  python scripts/chat_copilot.py --patch ch2_tmc_patch_001_r25000_c4000
  python scripts/chat_copilot.py --prompt "What is the safest landing zone in Patch 001?"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.navigation_interface.chatbot import LunarMissionChatbot


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Lunar Mission Copilot Chatbot CLI")
    parser.add_argument("--patch", default="ch2_tmc_patch_001_r25000_c4000", help="Active terrain patch ID")
    parser.add_argument("--prompt", type=str, default=None, help="Single-turn question to ask")
    parser.add_argument("--model", type=str, default="llama-3.3-70b-versatile", help="Groq model ID")
    args = parser.parse_args()

    bot = LunarMissionChatbot(model=args.model)

    if args.prompt:
        print(f"\n👨‍🚀 Flight Director: {args.prompt}")
        print(f"📡 Querying Groq LLM ({bot.model}) with mission context for [{args.patch}]...\n")
        response = bot.chat(args.prompt, active_patch_id=args.patch)
        print(f"🤖 Copilot:\n{response}\n")
        return 0

    print("=" * 72)
    print(" 🛰️  ISRO LUNAR MISSION AI COPILOT — GROUND CONTROL TERMINAL")
    print(f" Powered by Groq LLM: {bot.model}")
    print(f" Active Lunar Patch:  {args.patch}")
    print(" Type 'exit' or 'quit' to end session.")
    print("=" * 72 + "\n")

    history = []
    while True:
        try:
            user_input = input("👨‍🚀 [Mission Control] > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                print("\n🛰️  Ending mission copilot session. Standby.")
                break

            print("\n🤖 [Copilot is thinking...]")
            reply = bot.chat(user_input, active_patch_id=args.patch, history=history)
            print(f"\n{reply}\n" + "-" * 72 + "\n")

            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": reply})

        except (KeyboardInterrupt, EOFError):
            print("\n\nSession terminated.")
            break

    return 0


if __name__ == "__main__":
    sys.exit(main())
