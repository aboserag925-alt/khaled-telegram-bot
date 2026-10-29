"""Arabic text normalisation, automatic section choice and session number."""
import re

from config import DEFAULT_CATEGORY

_DIACRITICS = re.compile("[\u064b-\u065f\u0670\u0640]")
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def normalize(text):
    text = (text or "").translate(_DIGITS)
    text = _DIACRITICS.sub("", text)
    for src in "أإآٱ":
        text = text.replace(src, "ا")
    text = text.replace("ى", "ي").replace("ة", "ه")
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


# Order matters: the first rule that matches wins.
RULES = [
    ("عظماء الإسلام", ["عظماء"]),
    ("عقائد أهل السنة والعقيدة الواسطية", ["الواسطيه", "عقيده", "عقائد"]),
    ("أصول الفقه", ["اصول الفقه"]),
    ("أصول التفسير", ["اصول التفسير", "مناهج البيان", "قواعد فهم القران", "التفسير"]),
    ("مصطلح الحديث", ["مصطلح", "نخبه الفكر", "علم الحديث"]),
    ("شرح صحيح مسلم", ["صحيح مسلم", "مسلم"]),
    ("السيرة", ["السيره", "سيره"]),
    ("الفقه", ["الفقه", "فقه"]),
]


def classify(title):
    norm = normalize(title)
    for category, words in RULES:
        if any(w in norm for w in words):
            return category
    return DEFAULT_CATEGORY


_SESSION = re.compile(r"(?:المجلس|مجلس|الدرس|درس|الحلقه|حلقه)\s*(?:رقم\s*)?(\d+)")


def session_number(title):
    match = _SESSION.search(normalize(title))
    return int(match.group(1)) if match else None
