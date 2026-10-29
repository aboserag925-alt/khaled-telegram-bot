"""Broadcast schedule, read from schedule.json so it can be edited without code."""
import json

# Python weekday(): Monday = 0.
DAY_BY_WEEKDAY = ["الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
WEEK_ORDER = ["السبت", "الأحد", "الإثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة"]


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def day_name(weekday):
    return DAY_BY_WEEKDAY[weekday]


def format_day(data, day):
    items = data["days"].get(day, [])
    if not items:
        return f"{day}: لا يوجد بث"
    return f"{day}: " + " + ".join(items)


def format_week(data, today_weekday=None):
    lines = [
        "جدول البث الأسبوعي",
        f"الساعة {data['egypt_time']} بتوقيت مصر = {data['mecca_time']} بتوقيت مكة",
        "",
    ]
    today = day_name(today_weekday) if today_weekday is not None else None
    for day in WEEK_ORDER:
        if day in data["days"]:
            mark = "  (اليوم)" if day == today else ""
            lines.append(format_day(data, day) + mark)
    return "\n".join(lines)
