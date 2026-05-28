"""ASCII banners for Nyx startup (OS-specific + branding)."""

from __future__ import annotations

import platform

NYX_LOGO = r"""
    ███╗   ██╗██╗   ██╗██╗  ██╗
    ████╗  ██║╚██╗ ██╔╝╚██╗██╔╝
    ██╔██╗ ██║ ╚████╔╝  ╚███╔╝
    ██║╚██╗██║  ╚██╔╝   ██╔██╗
    ██║ ╚████║   ██║   ██╔╝ ██╗
    ╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝
"""

OS_BANNERS: dict[str, str] = {
    "Linux": r"""
     __    _  ___   _   ____
    |  |  | ||   \ | | / ___|
    |  |  | || |\ \| | \___ \
    |  |__| || | \   |  ___) |
    |_______||_|  \__| |____/
    """,
    "Darwin": r"""
    __  __     __
   / / / /__  / /_  ____
  / /_/ / _ \/ __ \/ __ \
 / __  /  __/ /_/ / /_/ /
/_/ /_/\___/_.___/\____/
    """,
    "Windows": r"""
    __      ___ __  __
    \ \    / (_)  \/  |
     \ \  / /| | |\/| |
      \ \/ / | | |  | |
       \  /  |_|_|  |_|
        \/
    """,
}

DEFAULT_OS_BANNER = r"""
    ___  ____
   / _ \| __ )
  | | | |  _ \
  | |_| | |_) |
   \___/|____/
"""


def os_banner() -> str:
    system = platform.system()
    return OS_BANNERS.get(system, DEFAULT_OS_BANNER)


def build_welcome_markup(agent_name: str = "Nyx") -> str:
    system = platform.system()
    release = platform.release()
    machine = platform.machine()
    return (
        f"[bold #7aa2f7]{NYX_LOGO}[/]\n"
        f"[dim]{os_banner()}[/]\n"
        f"[bold #bb9af7]{agent_name}[/] — terminal agent on "
        f"[cyan]{system}[/] [dim]{release} ({machine})[/]\n"
        f"[dim]Created by · Rzy · © Cohere[/]\n\n"
        "Type a message below. [bold]Ctrl+S[/] settings · "
        "[bold]Ctrl+L[/] clear · [bold]Ctrl+C[/] quit"
    )
