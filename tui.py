from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, Input, Static
from textual.containers import VerticalScroll
from rich.markup import escape
import asyncio
import sys
sys.path.insert(0, ".")

from src.core import nyxen

AI = nyxen(
    api_key="jADyfv6mP1ieilwk9swmx9cYvYx67OscByreAm3x",
    memory_file="Nyx_memory.json"
)


class NyxChat(App):
    CSS = """
    Screen {
        background: #1a1b26;
    }

    #chat-view {
        border: solid #7aa2f7;
        margin: 1 1 0 1;
        height: 1fr;
        min-height: 10;
        background: #1a1b26;
    }

    .msg {
        margin: 1 2;
        padding: 1 2;
        width: 80%;
    }

    .user {
        background: #24283b;
        color: #c0caf5;
        border-left: solid #7aa2f7;
    }

    .ai {
        background: #1a1b26;
        color: #c0caf5;
        border-left: solid #bb9af7;
    }

    #chat-input {
        border: solid #bb9af7;
        margin: 0 1 1 1;
        background: #1a1b26;
        color: #c0caf5;
        padding: 0 2;
    }

    #chat-input:focus {
        background: #1f2335;
    }

    Header {
        background: #7aa2f7;
        color: #1a1b26;
        text-style: bold;
    }

    Footer {
        background: #24283b;
        color: #565f89;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+l", "clear", "Clear", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with VerticalScroll(id="chat-view"):
            yield Static(
                "Welcome to [bold #7aa2f7]Nyx[/] \u2014 your AI assistant.\n"
                "Type a message and press [bold]Enter[/] to start.\n"
                "Use [bold]Ctrl+L[/] to clear, [bold]Ctrl+C[/] to quit.",
                classes="msg ai",
            )
        yield Input(
            placeholder="Type a message... (Enter to send)",
            id="chat-input",
        )
        yield Footer()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user_text = event.value.strip()
        if not user_text:
            return

        self.query_one("#chat-input", Input).clear()
        chat_view = self.query_one("#chat-view", VerticalScroll)

        user_msg = Static(
            f"[bold #7aa2f7]You[/]\n{user_text}",
            classes="msg user",
        )
        await chat_view.mount(user_msg)
        user_msg.scroll_visible()

        ai_msg = Static(
            "[bold #bb9af7]Nyxen[/]",
            classes="msg ai",
        )
        await chat_view.mount(ai_msg)
        ai_msg.scroll_visible()

        try:
            response = await asyncio.to_thread(AI.generate_response, user_text)
        except Exception as e:
            response = f"Error: {e}"

        prefix = "[bold #bb9af7]Nyxen[/]\n"
        safe = escape(response)
        await self._typewriter(ai_msg, prefix, safe)
        ai_msg.scroll_visible()

    async def _typewriter(
        self, widget: Static, prefix: str, text: str, delay: float = 0.012
    ) -> None:
        n = len(text)
        if n < 200:
            step = 1
        elif n < 600:
            step = 3
        else:
            step = 6
        for i in range(0, n, step):
            end = min(i + step, n)
            widget.update(f"{prefix}{text[:end]}")
            await asyncio.sleep(delay)

    async def action_clear(self) -> None:
        chat_view = self.query_one("#chat-view", VerticalScroll)
        await chat_view.remove_children()
        await chat_view.mount(Static(
            "Chat cleared. [bold #e0af68]Ctrl+L[/] to clear again.",
            classes="msg ai",
        ))


if __name__ == "__main__":
    app = NyxChat()
    app.run()
