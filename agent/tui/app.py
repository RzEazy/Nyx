import asyncio
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from rich.markup import escape
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Footer, Input, Label, Select, Static
from textual import work

from agent.agent.loop import AgentLoop
from agent.config import Settings, clear_settings_cache, get_provider, get_settings
from agent.memory.db import MemoryDB
from agent.providers.base import LLMProvider
from agent.tui.banner import build_welcome_markup

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"


class ChatView(ScrollableContainer):
    """Scrollable chat area with message bubbles."""

    DEFAULT_CSS = """
    ChatView {
        height: 1fr;
    }
    """

    async def add_user(self, text: str) -> None:
        widget = Static(f"[bold cyan]You[/]\n{escape(text)}", classes="bubble-user")
        await self.mount(widget)
        self.scroll_end(animate=False)

    async def add_agent(self, prefix: str = "") -> Static:
        widget = Static(prefix or "[bold white]Nyx[/]", classes="bubble-agent")
        await self.mount(widget)
        self.scroll_end(animate=False)
        return widget

    async def add_tool(self, title: str, body: str) -> None:
        widget = Static(
            f"[dim yellow]{escape(title)}[/]\n{escape(body)}",
            classes="bubble-tool",
        )
        await self.mount(widget)
        self.scroll_end(animate=False)

    async def add_system(self, markup: str) -> None:
        widget = Static(markup, classes="bubble-welcome")
        await self.mount(widget)
        self.scroll_end(animate=False)

    async def clear_messages(self) -> None:
        await self.remove_children()


class StatusBar(Static):
    """Reactive status line for provider, model, and token estimate."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.token_count = 0

    def update_status(
        self,
        provider: str,
        model: str,
        tokens: int | None = None,
    ) -> None:
        if tokens is not None:
            self.token_count = tokens
        self.update(
            f"♦ Nyx · provider: {provider} · model: {model} · tokens: ~{self.token_count}"
        )


@dataclass
class SudoPromptResult:
    password: str | None
    remember: bool = False


class SudoPasswordModal(ModalScreen[SudoPromptResult]):
    """Prompt for the user's sudo password when a command requires elevated privileges."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, command: str) -> None:
        super().__init__()
        self._command = command

    def compose(self) -> ComposeResult:
        preview = self._command if len(self._command) < 120 else self._command[:117] + "..."
        with Vertical(id="sudo-dialog"):
            yield Label("[bold #e0af68]Sudo password required[/]")
            yield Label("Command:")
            yield Static(preview, id="sudo-cmd-preview")
            yield Label("System password (not sent to the AI):")
            yield Input(
                id="sudo-password-input",
                password=True,
                placeholder="Enter your password",
            )
            yield Checkbox("Remember for this session", id="sudo-remember")
            with Horizontal(classes="settings-buttons"):
                yield Button("Run command", id="sudo-run-btn", variant="primary")
                yield Button("Cancel", id="sudo-cancel-btn")

    def on_mount(self) -> None:
        self.query_one("#sudo-password-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "sudo-password-input":
            self._submit()

    def action_cancel(self) -> None:
        self.dismiss(SudoPromptResult(password=None))

    def _submit(self) -> None:
        password = self.query_one("#sudo-password-input", Input).value
        remember = self.query_one("#sudo-remember", Checkbox).value
        self.dismiss(SudoPromptResult(password=password, remember=remember))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "sudo-cancel-btn":
            self.action_cancel()
            return
        if event.button.id == "sudo-run-btn":
            self._submit()


class SettingsModal(ModalScreen[bool]):
    """Switch provider and API key; persist to .env."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    SettingsModal {
        align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        settings = get_settings()
        provider = settings.provider
        if provider not in ("cohere", "openai", "anthropic"):
            provider = "cohere"
        with Vertical(id="settings-dialog"):
            yield Label("Settings")
            yield Label("Provider")
            yield Select(
                id="provider-select",
                options=[
                    ("Cohere", "cohere"),
                    ("OpenAI", "openai"),
                    ("Anthropic", "anthropic"),
                ],
                value=provider,
            )
            yield Label("API key (selected provider)")
            yield Input(
                id="api-key-input",
                password=True,
                placeholder="Paste API key",
            )
            with Horizontal(classes="settings-buttons"):
                yield Button("Save", id="save-btn", variant="primary")
                yield Button("Cancel", id="cancel-btn")

    def on_mount(self) -> None:
        settings = get_settings()
        key_map = {
            "cohere": settings.cohere_api_key,
            "openai": settings.openai_api_key,
            "anthropic": settings.anthropic_api_key,
        }
        self.query_one("#api-key-input", Input).value = key_map.get(
            settings.provider, ""
        )

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "provider-select":
            return
        if event.value is Select.BLANK:
            return
        settings = get_settings()
        key_map = {
            "cohere": settings.cohere_api_key,
            "openai": settings.openai_api_key,
            "anthropic": settings.anthropic_api_key,
        }
        self.query_one("#api-key-input", Input).value = key_map.get(
            str(event.value), ""
        )

    def action_cancel(self) -> None:
        self.dismiss(False)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(False)
            return
        if event.button.id != "save-btn":
            return

        provider = str(self.query_one("#provider-select", Select).value)
        api_key = self.query_one("#api-key-input", Input).value.strip()
        _write_env(provider, api_key)
        clear_settings_cache()
        self.dismiss(True)


def _write_env(provider: str, api_key: str) -> None:
    settings = get_settings()
    lines: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                lines[k.strip()] = v.strip()
    lines["PROVIDER"] = provider
    key_field = {
        "cohere": "COHERE_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }[provider]
    if api_key:
        lines[key_field] = api_key
    lines.setdefault("AGENT_NAME", settings.agent_name)
    lines.setdefault("COHERE_MODEL", settings.cohere_model)
    lines.setdefault("OPENAI_MODEL", settings.openai_model)
    lines.setdefault("ANTHROPIC_MODEL", settings.anthropic_model)
    lines.setdefault("CHROMA_PATH", settings.chroma_path)
    lines.setdefault("DB_PATH", settings.db_path)
    lines.setdefault("MAX_HISTORY", str(settings.max_history))

    out = "\n".join(f"{k}={v}" for k, v in lines.items()) + "\n"
    ENV_PATH.write_text(out, encoding="utf-8")
    os.environ["PROVIDER"] = provider
    os.environ[key_field] = api_key


class AgentApp(App):
    """Nyx terminal agent — mouse disabled to prevent stray escape chars in the input."""

    CSS_PATH = "styles.tcss"
    TITLE = "Nyx"
    ENABLE_MOUSE = False

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+l", "clear", "Clear", show=True),
        Binding("ctrl+s", "settings", "Settings", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.session_id = str(uuid.uuid4())
        self.memory = MemoryDB()
        self.provider: LLMProvider = get_provider()
        self.agent_loop = AgentLoop(
            provider=self.provider,
            memory=self.memory,
            session_id=self.session_id,
        )
        self._busy = False
        self._token_estimate = 0
        self._session_sudo_password: str | None = None
        self.agent_loop.sudo_password_provider = self._prompt_sudo_password

    def compose(self) -> ComposeResult:
        settings = get_settings()
        yield Static(id="header-bar")
        yield ChatView(id="chat-view")
        yield StatusBar(id="status-bar")
        with Horizontal(id="input-row"):
            yield Input(placeholder="> Ask Nyx anything...", id="chat-input")
            yield Button("Send", id="send-btn", variant="primary")
        yield Footer()

    async def on_mount(self) -> None:
        settings = get_settings()
        chat = self.query_one("#chat-view", ChatView)
        await chat.add_system(build_welcome_markup(settings.agent_name))
        self._refresh_status()

    def _refresh_status(self) -> None:
        settings = get_settings()
        model = getattr(self.provider, "model_name", settings.provider)
        self.query_one("#status-bar", StatusBar).update_status(
            settings.provider,
            model,
            self._token_estimate,
        )
        header = self.query_one("#header-bar", Static)
        header.update(
            f"[bold #7aa2f7]◆ {settings.agent_name}[/]  "
            f"[dim]·[/]  [cyan]{settings.provider}[/]  "
            f"[dim]· © Cohere · Rzy[/]"
        )

    async def _prompt_sudo_password(self, command: str) -> str | None:
        if self._session_sudo_password:
            return self._session_sudo_password
        chat = self.query_one("#chat-view", ChatView)
        await chat.add_tool(
            "sudo",
            f"Password required to run:\n{command}",
        )
        loop = asyncio.get_running_loop()
        future: asyncio.Future[SudoPromptResult | None] = loop.create_future()

        def on_dismiss(result: SudoPromptResult | None) -> None:
            if not future.done():
                future.set_result(result)

        self.push_screen(SudoPasswordModal(command), on_dismiss)
        result = await future
        if result and result.password:
            if result.remember:
                self._session_sudo_password = result.password
            return result.password
        await chat.add_tool("sudo", "Command cancelled (no password).")
        return None

    def _reinit_provider(self) -> None:
        clear_settings_cache()
        self.provider = get_provider()
        self.agent_loop.provider = self.provider
        self._refresh_status()

    def action_settings(self) -> None:
        self._open_settings_modal()

    @work(exclusive=True)
    async def _open_settings_modal(self) -> None:
        saved = await self.push_screen_wait(SettingsModal())
        if saved:
            self._reinit_provider()
            chat = self.query_one("#chat-view", ChatView)
            await chat.add_tool("system", "Settings saved. Provider reloaded.")

    async def action_clear(self) -> None:
        chat = self.query_one("#chat-view", ChatView)
        await chat.clear_messages()
        settings = get_settings()
        await chat.add_system(build_welcome_markup(settings.agent_name))
        self.session_id = str(uuid.uuid4())
        self.agent_loop.session_id = self.session_id
        self._token_estimate = 0
        self._session_sudo_password = None
        self._refresh_status()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "chat-input":
            await self._handle_send()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send-btn":
            await self._handle_send()

    async def _handle_send(self) -> None:
        if self._busy:
            return
        inp = self.query_one("#chat-input", Input)
        text = inp.value.strip()
        if not text:
            return
        inp.clear()
        self._busy = True
        asyncio.create_task(self._run_agent(text))

    async def _run_agent(self, user_text: str) -> None:
        chat = self.query_one("#chat-view", ChatView)
        status = self.query_one("#status-bar", StatusBar)
        settings = get_settings()

        try:
            await chat.add_user(user_text)
            agent_widget = await chat.add_agent("[bold #bb9af7]Nyx[/]\n")
            prefix = "[bold #bb9af7]Nyx[/]\n"

            self._token_estimate += max(1, len(user_text) // 4)

            final = await self.agent_loop.run(user_text)

            for ev in self.agent_loop.events[:-1]:
                if ev.kind == "tool_call":
                    await chat.add_tool(f"tool: {ev.tool_name}", ev.content)
                elif ev.kind == "tool_result":
                    await chat.add_tool(f"result: {ev.tool_name}", ev.content)

            await self._typewriter(agent_widget, prefix, escape(final))

            self._token_estimate += max(1, len(final) // 4)
            model = getattr(self.provider, "model_name", settings.provider)
            status.update_status(settings.provider, model, self._token_estimate)
            chat.scroll_end(animate=False)
        except Exception as e:
            await chat.add_tool("error", str(e))
        finally:
            self._busy = False

    async def _typewriter(
        self, widget: Static, prefix: str, text: str, delay: float = 0.008
    ) -> None:
        n = len(text)
        step = 1 if n < 200 else (3 if n < 600 else 6)
        for i in range(0, n, step):
            widget.update(f"{prefix}{text[: min(i + step, n)]}")
            await asyncio.sleep(delay)


def run_app() -> None:
    AgentApp().run()
