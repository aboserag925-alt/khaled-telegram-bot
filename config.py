"""Bot settings. Everything secret or unknown comes from environment variables."""
import os


def _ids(name):
    out = set()
    for part in os.environ.get(name, "").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            out.add(int(part))
    return out


# The token is read only from the environment. Never put it in code.
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Bot name is not decided yet. Set BOT_NAME when it is.
BOT_NAME = os.environ.get("BOT_NAME", "")

SIGNATURE = "صُنع بواسطة «فارس السنة»"

DB_PATH = os.environ.get("DB_PATH", "data/bot.db")
SCHEDULE_PATH = os.environ.get("SCHEDULE_PATH", "schedule.json")

# Telegram user ids allowed to add recordings and change a section.
ADMIN_IDS = _ids("ADMIN_IDS")
# Chat or channel ids whose audio posts are archived automatically.
ARCHIVE_CHAT_IDS = _ids("ARCHIVE_CHAT_IDS")

# Real links are not available yet. Leave empty until the owner provides them.
LINKS = {
    "يوتيوب": os.environ.get("YOUTUBE_URL", ""),
    "تيك توك": os.environ.get("TIKTOK_URL", ""),
    "تليجرام": os.environ.get("TELEGRAM_CHANNEL_URL", ""),
}

DEFAULT_CATEGORY = "منوعات"

CATEGORIES = [
    "شرح صحيح مسلم",
    "مصطلح الحديث",
    "أصول التفسير",
    "عقائد أهل السنة والعقيدة الواسطية",
    "أصول الفقه",
    "الفقه",
    "السيرة",
    "عظماء الإسلام",
    "منوعات",
]

PAGE_SIZE = 10
