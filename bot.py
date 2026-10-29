"""Telegram bot entry point. Run with: python bot.py"""
import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          MessageHandler, filters)

import config
import db
import schedule

CONN = None
SCHEDULE = None


def signed(text):
    return f"{text}\n\n{config.SIGNATURE}"


def is_admin(update):
    user = update.effective_user
    return bool(user and user.id in config.ADMIN_IDS)


def list_markup(rows, nav=None):
    buttons = [[InlineKeyboardButton(r["title"][:60], callback_data=f"get:{r['id']}")]
               for r in rows]
    if nav:
        buttons.append([InlineKeyboardButton(t, callback_data=d) for t, d in nav])
    return InlineKeyboardMarkup(buttons)


async def reply(update, text, markup=None):
    await update.effective_message.reply_text(signed(text), reply_markup=markup)


async def cmd_start(update, context, arg):
    name = f" {config.BOT_NAME}" if config.BOT_NAME else ""
    await reply(update, (
        f"أهلًا بك في بوت جروب الدكتور خالد الحارس{name}.\n"
        "/بحث كلمة: بحث في عناوين التسجيلات\n"
        "/قسم اسم القسم: عرض قسم\n"
        "/جديد: آخر التسجيلات\n"
        "/جدول: جدول البث\n"
        "/روابط: روابط القناة"))


async def cmd_search(update, context, arg):
    if not arg:
        return await reply(update, "اكتب كلمة البحث بعد الأمر. مثال: /بحث الإيمان")
    rows = db.search(CONN, arg)
    if not rows:
        return await reply(update, "لم أجد تسجيلات بهذا العنوان. جرّب كلمة أقصر.")
    await reply(update, f"نتائج البحث عن «{arg}»:", list_markup(rows))


async def cmd_section(update, context, arg):
    if not arg:
        lines = [f"{r['name']} ({r['n']})" for r in db.counts(CONN)]
        return await reply(update, "الأقسام:\n" + "\n".join(lines) +
                           "\n\nاكتب /قسم ثم اسم القسم.")
    cat = db.find_category(CONN, arg)
    if not cat:
        return await reply(update, "لا يوجد قسم بهذا الاسم. اكتب /قسم لعرض الأقسام.")
    await send_section(update, cat["id"], cat["name"], 0)


async def send_section(update, cat_id, name, offset, edit=False):
    rows = db.by_category(CONN, cat_id, config.PAGE_SIZE + 1, offset)
    more = len(rows) > config.PAGE_SIZE
    rows = rows[:config.PAGE_SIZE]
    if not rows:
        text, markup = f"قسم «{name}» لا يحتوي تسجيلات بعد.", None
    else:
        nav = []
        if offset > 0:
            nav.append(("السابق", f"sec:{cat_id}:{max(offset - config.PAGE_SIZE, 0)}"))
        if more:
            nav.append(("التالي", f"sec:{cat_id}:{offset + config.PAGE_SIZE}"))
        text, markup = f"قسم «{name}»:", list_markup(rows, nav)
    if edit:
        await update.callback_query.edit_message_text(signed(text), reply_markup=markup)
    else:
        await reply(update, text, markup)


async def cmd_new(update, context, arg):
    rows = db.latest(CONN)
    if not rows:
        return await reply(update, "لا توجد تسجيلات مضافة بعد.")
    await reply(update, "آخر التسجيلات:", list_markup(rows))


async def cmd_schedule(update, context, arg):
    today = datetime.now(ZoneInfo("Africa/Cairo")).weekday()
    await reply(update, schedule.format_week(SCHEDULE, today))


async def cmd_links(update, context, arg):
    lines = [f"{name}: {url}" for name, url in config.LINKS.items() if url]
    if not lines:
        return await reply(update, "الروابط لم تُضف بعد.")
    await reply(update, "روابط القناة:\n" + "\n".join(lines))


async def cmd_setcat(update, context, arg):
    """Admin only. Usage: /تصنيف 12 الفقه"""
    if not is_admin(update):
        return await reply(update, "هذا الأمر للمشرف فقط.")
    parts = arg.split(maxsplit=1)
    if len(parts) != 2 or not parts[0].isdigit():
        return await reply(update, "الاستخدام: /تصنيف رقم_التسجيل اسم_القسم")
    cat = db.find_category(CONN, parts[1])
    if not cat:
        return await reply(update, "لا يوجد قسم بهذا الاسم.")
    if db.set_category(CONN, int(parts[0]), cat["name"]):
        await reply(update, f"تم نقل التسجيل {parts[0]} إلى قسم «{cat['name']}».")
    else:
        await reply(update, "لا يوجد تسجيل بهذا الرقم.")


COMMANDS = {
    "start": cmd_start, "بداية": cmd_start,
    "search": cmd_search, "بحث": cmd_search,
    "section": cmd_section, "قسم": cmd_section,
    "new": cmd_new, "جديد": cmd_new,
    "schedule": cmd_schedule, "جدول": cmd_schedule,
    "links": cmd_links, "روابط": cmd_links,
    "setcat": cmd_setcat, "تصنيف": cmd_setcat,
}

CMD_PATTERN = re.compile(r"^/(\S+?)(?:@\w+)?(?:\s+(.*))?$", re.DOTALL)


async def arabic_command(update, context):
    """Telegram only understands Latin command names, so Arabic ones are parsed here."""
    match = CMD_PATTERN.match(update.effective_message.text or "")
    if not match:
        return
    handler = COMMANDS.get(match.group(1))
    if handler:
        await handler(update, context, (match.group(2) or "").strip())


def latin(handler):
    async def wrapper(update, context):
        await handler(update, context, " ".join(context.args or []))
    return wrapper


async def on_button(update, context):
    query = update.callback_query
    await query.answer()
    kind, _, rest = query.data.partition(":")
    if kind == "get":
        rec = db.get(CONN, int(rest))
        if not rec:
            return
        caption = signed(rec["title"])
        chat = query.message.chat_id
        if rec["kind"] == "voice":
            await context.bot.send_voice(chat, rec["file_id"], caption=caption)
        elif rec["kind"] == "document":
            await context.bot.send_document(chat, rec["file_id"], caption=caption)
        else:
            await context.bot.send_audio(chat, rec["file_id"], caption=caption)
    elif kind == "sec":
        cat_id, _, offset = rest.partition(":")
        row = CONN.execute("SELECT name FROM categories WHERE id = ?", (int(cat_id),)).fetchone()
        if row:
            await send_section(update, int(cat_id), row["name"], int(offset), edit=True)


async def on_media(update, context):
    """Archive audio sent by an admin or posted in an archive chat.
    Files are not re-uploaded: only the Telegram file_id is stored."""
    msg = update.effective_message
    if not (is_admin(update) or msg.chat_id in config.ARCHIVE_CHAT_IDS):
        return
    if msg.audio:
        media, kind, title = msg.audio, "audio", msg.audio.title or msg.audio.file_name
    elif msg.voice:
        media, kind, title = msg.voice, "voice", None
    else:
        media, kind, title = msg.document, "document", msg.document.file_name
    if msg.caption:
        title = msg.caption.strip().splitlines()[0]
    title = re.sub(r"\.(mp3|m4a|ogg|opus|wav|aac)$", "", title or "", flags=re.I)
    result = db.add_recording(CONN, title, media.file_id, media.file_unique_id, kind)
    if result and is_admin(update):
        await reply(update, f"تم تسجيل الملف رقم {result[0]} في قسم «{result[1]}».\n"
                    "لتغيير القسم: /تصنيف الرقم اسم_القسم")


def build_app():
    global CONN, SCHEDULE
    if not config.BOT_TOKEN:
        raise SystemExit("المتغير BOT_TOKEN غير موجود. ضعه في إعدادات الاستضافة.")
    CONN = db.connect(config.DB_PATH)
    SCHEDULE = schedule.load(config.SCHEDULE_PATH)
    app = Application.builder().token(config.BOT_TOKEN).build()
    for name in ("start", "search", "section", "new", "schedule", "links", "setcat"):
        app.add_handler(CommandHandler(name, latin(COMMANDS[name])))
    app.add_handler(MessageHandler(filters.Regex(r"^/\S*[\u0600-\u06FF]"), arabic_command))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(
        filters.AUDIO | filters.VOICE | filters.Document.AUDIO, on_media))
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build_app().run_polling()
