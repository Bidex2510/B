"""Life manager plugin - chat commands for emails, calls, calendar, briefings."""

import re
from jarvis.core.plugin_base import PluginBase


class LifeManagerPlugin(PluginBase):
    name = "life_manager"
    description = "Daily briefings, email management, call logs, calendar — your full life manager"

    TRIGGERS = [
        r"\b(morning\s+briefing|daily\s+briefing|brief\s+me)\b",
        r"\b(good\s+morning|good\s+evening|recap)\b",
        r"\b(any\s+(new\s+)?emails?|inbox|unread|email\s+digest)\b",
        r"\b(missed\s+calls?|any\s+calls?|call\s+log)\b",
        r"\b(my\s+calendar|today'?s?\s+(events?|schedule)|what'?s?\s+on\s+today)\b",
        r"\b(upcoming\s+events?|next\s+week)\b",
        r"\b(send\s+sms|text\s+message|make\s+a\s+call|call\s+\+?\d)\b",
    ]

    def can_handle(self, text: str) -> bool:
        return any(re.search(p, text, re.IGNORECASE) for p in self.TRIGGERS)

    def handle(self, text: str) -> str:
        lower = text.lower()

        if "morning" in lower and ("briefing" in lower or "good morning" in lower or "brief me" in lower):
            return self._briefing_help("morning")
        if "evening" in lower or "recap" in lower or "good evening" in lower:
            return self._briefing_help("evening")
        if "email" in lower or "inbox" in lower or "unread" in lower:
            return self._email_help()
        if "call" in lower:
            return self._call_help()
        if "calendar" in lower or "schedule" in lower or "events" in lower:
            return self._calendar_help()
        if "sms" in lower or "text" in lower:
            return self._sms_help()

        return self._overview()

    def _briefing_help(self, period: str) -> str:
        if period == "morning":
            return (
                "Morning briefing ready, sir. Hit GET /api/briefing/morning?city=YourCity for:\n"
                "  • Weather forecast\n"
                "  • Today's calendar events\n"
                "  • Priority unread emails\n"
                "  • Missed calls overnight\n"
                "  • Top news headlines\n"
                "  • Today's TikTok content to publish\n"
                "  • AI executive summary (3 sentences)\n\n"
                "Or open the dashboard and tap 'Morning Briefing'."
            )
        return (
            "Evening recap available at GET /api/briefing/evening, sir.\n"
            "Includes task completion, call/SMS counts, unread inbox, and tomorrow prep."
        )

    def _email_help(self) -> str:
        return (
            "Email controls, sir:\n"
            "  • /api/email/inbox — recent emails\n"
            "  • /api/email/unread — unread count\n"
            "  • /api/email/digest — AI-summarized briefing\n"
            "  • /api/email/priority — urgent emails flagged\n"
            "  • /api/email/draft-reply — AI-write a reply to any email\n"
            "  • /api/email/send — send a new email\n\n"
            "Requires GMAIL_ACCESS_TOKEN configured. See /api/email/setup."
        )

    def _call_help(self) -> str:
        return (
            "Phone controls, sir (Twilio):\n"
            "  • /api/phone/call — make an outbound call\n"
            "  • /api/phone/sms — send a text message\n"
            "  • /api/phone/calls — call history\n"
            "  • /api/phone/missed — missed calls\n"
            "  • /api/phone/voice-webhook — auto-answer incoming with voicemail + transcription\n\n"
            "Setup at /api/phone/setup — Twilio free trial gives $15 credit."
        )

    def _calendar_help(self) -> str:
        return (
            "Calendar controls, sir:\n"
            "  • /api/calendar/today — today's events\n"
            "  • /api/calendar/upcoming?days=7 — next week\n"
            "  • /api/calendar/create — schedule a new event\n\n"
            "Requires Google OAuth. See /api/calendar/setup."
        )

    def _sms_help(self) -> str:
        return (
            "To send an SMS, POST to /api/phone/sms with:\n"
            "  { \"to\": \"+14155551234\", \"body\": \"your message\" }\n\n"
            "Same for calls at /api/phone/call (add 'say' field for TTS)."
        )

    def _overview(self) -> str:
        return (
            "Your Life Manager is ready, sir. Try:\n"
            "  • 'morning briefing' — full daily overview\n"
            "  • 'any new emails' — inbox status\n"
            "  • 'missed calls' — phone log\n"
            "  • 'what's on my calendar' — today's events\n"
            "  • 'evening recap' — end-of-day summary\n\n"
            "Or use the dashboard panels for a visual view."
        )
