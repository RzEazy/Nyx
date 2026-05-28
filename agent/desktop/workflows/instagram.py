"""Instagram DM workflow — send messages to Instagram contacts."""

import time

from ..config import DesktopConfig
from ..utils import get_logger

log = get_logger("workflows.instagram")


class InstagramWorkflow:
    def __init__(self, cfg: DesktopConfig, mouse, keyboard, detector, browser_nav, browser_search):
        self.cfg = cfg
        self.mouse = mouse
        self.keyboard = keyboard
        self.detector = detector
        self.nav = browser_nav
        self.search = browser_search

    async def send_dm(self, recipient: str, message: str) -> str:
        """Full pipeline: open Instagram → navigate to DMs → search user → send message."""
        log.info("Instagram DM: send '%s' to '%s'", message, recipient)

        # 1. Navigate to Instagram
        self.nav.go_to_and_wait("instagram.com", 4)
        self._capture("after_instagram_load")

        # 2. Check for login prompt
        login_found = self.detector.find_any(["log in", "sign in", "login"])
        if login_found:
            log.warning("Login prompt detected — may need manual login")
            return "LOGIN_REQUIRED: Instagram login page detected"

        # 3. Navigate to DMs
        dm_icons = self.detector.find_any(["messages", "direct", "inbox"])
        if dm_icons:
            self.mouse.click_element(dm_icons)
            log.info("Clicked DMs icon")
            time.sleep(3)
        else:
            self.nav.go_to_and_wait("instagram.com/direct/inbox", 3)

        self._capture("after_dm_open")

        # 4. Search for recipient
        time.sleep(2)
        search_box = self.detector.find_any(["search", "find", "to:"])
        if search_box:
            self.mouse.click_element(search_box)
            time.sleep(0.5)
            self.keyboard.type(recipient, interval=0.05)
            time.sleep(2)
            self._capture("after_user_search")
        else:
            log.warning("Could not find DM search box")
            return "FAILED: Could not find DM search"

        # 5. Click matching conversation
        user_found = self.detector.find_text(recipient)
        if user_found:
            self.mouse.click_element(user_found)
            time.sleep(2)
            self._capture("after_chat_open")
        else:
            # Try clicking first result
            results = self.detector.find_all_text()
            chat_results = [r for r in results if len(r["text"]) > 2 and len(r["text"]) < 30]
            if chat_results:
                self.mouse.click_element(chat_results[0])
                time.sleep(2)
                self._capture("after_chat_open_fallback")

        # 6. Find message input and type
        input_field = self.detector.find_input_field()
        if not input_field:
            input_field = self.detector.find_any(["message", "type a message", "write"])
        if input_field:
            self.mouse.click_element(input_field)
            time.sleep(0.5)
            self.keyboard.type(message, interval=0.03)
            time.sleep(0.3)
            self._capture("after_typing")
        else:
            log.warning("Could not find message input")
            return "FAILED: No message input found"

        # 7. Send
        send_btn = self.detector.find_any(["send", "→"])
        if send_btn:
            self.mouse.click_element(send_btn)
            log.info("Clicked Send button")
        else:
            self.keyboard.press("enter")

        time.sleep(1)
        self._capture("after_send")
        log.info("DM sent to %s", recipient)

        # 8. Verify
        sent_verify = self.detector.find_text(message[:20])
        if sent_verify:
            return f"SUCCESS: Message sent to {recipient}"
        return f"SENT: Message sent to {recipient} (verification incomplete)"

    def _capture(self, tag: str):
        try:
            from ..vision import ScreenCapture
            cap = ScreenCapture(self.cfg)
            return cap.save(tag)
        except Exception:
            return ""
