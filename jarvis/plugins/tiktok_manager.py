"""TikTok content manager plugin - video ideas, scripts, captions, calendar."""

import re
import random
from jarvis.core.plugin_base import PluginBase


class TikTokManagerPlugin(PluginBase):
    name = "tiktok_manager"
    description = "Generate TikTok video ideas, scripts, captions, and content calendar (Sports, Wholesome, AI)"

    TRIGGERS = [
        r"\b(tiktok|tik\s*tok)\b",
        r"\b(video\s+idea|video\s+script|content\s+idea)\b",
        r"\b(sports\s+video|wholesome\s+video|ai\s+video)\b",
        r"\b(caption|hashtag|content\s+calendar)\b",
        r"\b(viral\s+content|short\s+video|reel)\b",
    ]

    SPORTS_IDEAS = [
        "5 mind-blowing sports facts nobody talks about",
        "The greatest comeback in [sport] history explained in 60 seconds",
        "What pro athletes eat before a big game",
        "The training secret that made [athlete] great",
        "Rating viral sports moments: real or fake?",
        "The most underrated sport you should be watching",
        "Why [team] will win the championship this year",
        "Behind the scenes: athlete warm-up routines",
        "Teaching myself [sport] in 30 days - day 1",
        "Sports records that will never be broken",
    ]

    WHOLESOME_IDEAS = [
        "Dog sees their owner for the first time in months",
        "Grandparents react to modern music challenge",
        "Kids explain what love means - their answers are perfect",
        "Random acts of kindness that restore faith in humanity",
        "The world's kindest bus driver goes viral",
        "Animals meeting each other for the first time",
        "Teachers who changed students' lives forever",
        "Community helps stranger in need - wholesome ending",
        "Baby's first reaction to [fruit/animal/music]",
        "Surprise reunion that will make you tear up",
    ]

    AI_IDEAS = [
        "I asked AI to build my website - here's what happened",
        "5 AI tools that are actually completely free",
        "AI vs Human: who does [task] better?",
        "The ChatGPT prompt that changed how I work",
        "I used AI to plan my entire week - results were crazy",
        "The AI tool quietly replacing [job] right now",
        "Build a chatbot in 5 minutes with zero code",
        "Testing the newest AI model so you don't have to",
        "How I built my own JARVIS assistant for free",
        "AI predicted this 5 years ago... it came true",
    ]

    def can_handle(self, text: str) -> bool:
        return any(re.search(p, text, re.IGNORECASE) for p in self.TRIGGERS)

    def handle(self, text: str) -> str:
        lower = text.lower()

        if any(w in lower for w in ["idea", "suggest", "what should", "give me"]):
            category = self._detect_category(lower)
            return self._get_ideas(category)

        if any(w in lower for w in ["calendar", "schedule", "week", "plan"]):
            return self._get_weekly_calendar()

        if any(w in lower for w in ["hashtag", "caption", "tag"]):
            category = self._detect_category(lower)
            return self._get_caption_tips(category)

        if any(w in lower for w in ["trend", "viral", "hot"]):
            return self._get_trending()

        return self._get_overview()

    def _detect_category(self, text: str) -> str:
        if "sport" in text:
            return "sports"
        if "wholesome" in text or "feel" in text or "kind" in text:
            return "wholesome"
        if " ai " in text or "tech" in text or "artificial" in text:
            return "ai"
        return "all"

    def _get_ideas(self, category: str) -> str:
        lines = ["Here are your TikTok video ideas, sir:\n"]

        if category in ("sports", "all"):
            lines.append("SPORTS:")
            for idea in random.sample(self.SPORTS_IDEAS, 3):
                lines.append(f"  • {idea}")

        if category in ("wholesome", "all"):
            lines.append("\nWHOLESOME:")
            for idea in random.sample(self.WHOLESOME_IDEAS, 3):
                lines.append(f"  • {idea}")

        if category in ("ai", "all"):
            lines.append("\nAI:")
            for idea in random.sample(self.AI_IDEAS, 3):
                lines.append(f"  • {idea}")

        lines.append("\nSay 'tiktok script for [idea]' to get a full script, sir.")
        return "\n".join(lines)

    def _get_weekly_calendar(self) -> str:
        schedule = [
            ("Monday", "9:00 AM", "AI", "AI tool spotlight or tutorial"),
            ("Tuesday", "7:00 PM", "Sports", "Sports recap or bold prediction"),
            ("Wednesday", "12:00 PM", "Wholesome", "Mid-week feel-good story"),
            ("Thursday", "6:00 PM", "AI", "AI tips & tricks"),
            ("Friday", "5:00 PM", "Sports", "Weekend sports preview"),
            ("Saturday", "11:00 AM", "Wholesome", "Weekend feel-good / animal content"),
            ("Sunday", "3:00 PM", "AI", "Week in AI recap"),
        ]
        lines = ["Weekly TikTok Content Calendar, sir:\n"]
        for day, time, cat, idea in schedule:
            lines.append(f"  {day} ({time}): [{cat}] {idea}")
        lines.append("\nPosting 7x/week maximizes the algorithm. Consistency wins, sir.")
        return "\n".join(lines)

    def _get_caption_tips(self, category: str) -> str:
        tag_sets = {
            "sports": "#sports #athlete #fyp #viral #sportsedits #motivation #winning #champion",
            "wholesome": "#wholesome #heartwarming #fyp #viral #feelgood #kindness #love #inspiring",
            "ai": "#ai #artificialintelligence #tech #fyp #viral #future #aitools #chatgpt",
            "all": "#fyp #viral #trending #foryou #explore",
        }
        tags = tag_sets.get(category, tag_sets["all"])
        return (
            f"Caption strategy for {category.upper()} content, sir:\n\n"
            f"Hashtags: {tags}\n\n"
            f"Caption formula:\n"
            f"  [Hook] + [Context] + [CTA]\n\n"
            f"Example:\n"
            f"  'Nobody talks about this... [topic] will change everything 🤯\n"
            f"   Follow for more! Comment 'MORE' for part 2'\n\n"
            f"Best posting times: 9AM, 12PM, 7PM (audience's local time)"
        )

    def _get_trending(self) -> str:
        return (
            "Trending angles for your TikTok niches, sir:\n\n"
            "SPORTS:\n"
            "  • 'Did you know [athlete] almost quit before making it?'\n"
            "  • Controversial takes that spark debate\n"
            "  • 'Rating [famous athlete's] technique'\n\n"
            "WHOLESOME:\n"
            "  • Military homecoming reunions\n"
            "  • 'The nicest thing a stranger ever did'\n"
            "  • Pets comforting crying owners\n\n"
            "AI:\n"
            "  • Claude vs ChatGPT live comparison\n"
            "  • 'I automated my morning routine with AI'\n"
            "  • Free tools nobody knows about\n\n"
            "Hook rule: First 1-2 seconds decide everything, sir."
        )

    def _get_overview(self) -> str:
        return (
            "TikTok Manager ready, sir. I can help you with:\n\n"
            "  • 'tiktok ideas' - fresh video concepts\n"
            "  • 'sports video ideas' - sports content\n"
            "  • 'wholesome video ideas' - feel-good content\n"
            "  • 'ai video ideas' - tech/AI content\n"
            "  • 'tiktok calendar' - 7-day posting schedule\n"
            "  • 'tiktok captions' - hashtag strategy\n"
            "  • 'tiktok trending' - what's hot right now\n\n"
            "Use the dashboard TikTok panel for AI-generated scripts, sir."
        )
