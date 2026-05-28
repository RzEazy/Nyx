"""CLI entry point for the vision-driven desktop agent.

Usage:
    python -m agent.desktop "Open Chrome and go to Instagram"
    python -m agent.desktop --interactive "Send hello to Rahul on Instagram"
"""

import argparse
import asyncio
import sys


async def main():
    parser = argparse.ArgumentParser(description="Vision-driven desktop agent")
    parser.add_argument("task", nargs="?", default="", help="Natural-language task")
    parser.add_argument("--interactive", "-i", action="store_true", help="LLM-decides-each-step mode")
    args = parser.parse_args()

    if not args.task:
        parser.print_help()
        sys.exit(1)

    from .core import DesktopAgent

    agent = DesktopAgent()
    mode = "interactive" if args.interactive else "batch"
    print(f"\nDesktop Agent v2 — {mode} mode")
    print(f"Task: {args.task}\n")

    if args.interactive:
        result = await agent.run_interactive(args.task)
    else:
        result = await agent.run(args.task)

    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
