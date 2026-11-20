"""
PLC Ladder Telegram Bot
- /start  : shows a button that opens the Mini App (ladder editor)
- web_app_data : receives the ladder program from the Mini App,
                 validates it, and replies with:
                   * an ASCII ladder preview
                   * a generated IEC 61131-3 Structured Text (.st) file
"""

import asyncio
import html
import json
import logging
import os
import re

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BufferedInputFile,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "")  # e.g. https://username.github.io/plc-telegram-bot/

MAX_RUNGS = 50
COLS = 8

TAG_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,31}$")
TIME_RE = re.compile(r"^\d{1,6}(ms|s|m|h)$")
CONTACTS = {"NO", "NC"}
OUTPUTS = {"COIL", "SET", "RESET", "TON", "CTU"}
TYPES = CONTACTS | OUTPUTS


class PlcError(ValueError):
    """Raised when the ladder program is invalid."""


def parse_program(raw: str) -> list[list[dict]]:
    """Validate the JSON from the mini app and return a list of rungs.
    Each rung is a list of items (contacts..., output) with no gaps."""
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise PlcError("ساختار داده نامعتبر است")

    rungs_in = data.get("rungs")
    if not isinstance(rungs_in, list):
        raise PlcError("ساختار داده نامعتبر است")
    if len(rungs_in) > MAX_RUNGS:
        raise PlcError(f"حداکثر {MAX_RUNGS} ردیف مجاز است")

    rungs: list[list[dict]] = []
    for idx, rung in enumerate(rungs_in, 1):
        cells = rung.get("cells") if isinstance(rung, dict) else None
        if not isinstance(cells, list) or len(cells) > COLS:
            raise PlcError(f"ردیف {idx} نامعتبر است")

        items: list[dict] = []
        for cell in cells:
            if cell is None:  # empty cell = wire
                continue
            if not isinstance(cell, dict):
                raise PlcError(f"ردیف {idx}: خانه نامعتبر است")

            t = cell.get("type")
            if t not in TYPES:
                raise PlcError(f"ردیف {idx}: نوع «{t}» ناشناخته است")

            tag = str(cell.get("tag", "")).strip()
            param = str(cell.get("param", "")).strip()
            if not TAG_RE.match(tag):
                raise PlcError(f"ردیف {idx}: نام «{tag}» نامعتبر است")

            if t == "TON" and not TIME_RE.match(param):
                raise PlcError(f"ردیف {idx}: زمان TON نامعتبر است (مثال: 5s یا 500ms)")
            if t == "CTU" and not param.isdigit():
                raise PlcError(f"ردیف {idx}: مقدار CTU باید عدد صحیح باشد")

            items.append({"type": t, "tag": tag, "param": param})

        if not items:
            continue  # empty rung is ignored

        out_positions = [i for i, it in enumerate(items) if it["type"] in OUTPUTS]
        if len(out_positions) != 1 or out_positions[0] != len(items) - 1:
            raise PlcError(
                f"ردیف {idx}: هر ردیف باید دقیقاً یک خروجی داشته باشد و خروجی باید در انتهای ردیف باشد"
            )
        rungs.append(items)

    if not rungs:
        raise PlcError("برنامه خالی است")
    return rungs


def contact_expr(item: dict) -> str:
    return f"NOT {item['tag']}" if item["type"] == "NC" else item["tag"]


def to_ladder(rung: list[dict]) -> str:
    parts = []
    for it in rung:
        t, tag, p = it["type"], it["tag"], it["param"]
        if t == "NO":
            parts.append(f"[ {tag} ]")
        elif t == "NC":
            parts.append(f"[/ {tag} ]")
        elif t == "COIL":
            parts.append(f"( {tag} )")
        elif t == "SET":
            parts.append(f"(S {tag})")
        elif t == "RESET":
            parts.append(f"(R {tag})")
        elif t == "TON":
            parts.append(f"[TON {tag} PT={p}]")
        elif t == "CTU":
            parts.append(f"[CTU {tag} PV={p}]")
    return "|--" + "--".join(parts) + "--|"


def to_structured_text(rungs: list[list[dict]]) -> str:
    declarations: dict[str, str] = {}
    body: list[str] = []

    for n, rung in enumerate(rungs, 1):
        *conds, out = rung
        expr = " AND ".join(contact_expr(c) for c in conds) or "TRUE"
        t, tag, p = out["type"], out["tag"], out["param"]

        body.append(f"// Rung {n}")
        if t == "COIL":
            body.append(f"{tag} := {expr};")
        elif t == "SET":
            body.append(f"IF {expr} THEN {tag} := TRUE; END_IF;")
        elif t == "RESET":
            body.append(f"IF {expr} THEN {tag} := FALSE; END_IF;")
        elif t == "TON":
            declarations[tag] = f"    {tag} : TON;"
            body.append(f"{tag}(IN := {expr}, PT := T#{p});")
        elif t == "CTU":
            declarations[tag] = f"    {tag} : CTU;"
            body.append(f"{tag}(CU := {expr}, R := FALSE, PV := {p});")
        body.append("")

    header = [
        "// Generated by PLC Ladder Telegram Bot",
        "// Undeclared BOOL variables are assumed to be I/O or internal bits.",
        "PROGRAM Main",
    ]
    if declarations:
        header += ["VAR"] + list(declarations.values()) + ["END_VAR", ""]
    return "\n".join(header + body + ["END_PROGRAM", ""])


# ---------------------------------------------------------------- bot handlers

dp = Dispatcher()


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🛠 باز کردن نقشه‌کش PLC", web_app=WebAppInfo(url=WEBAPP_URL))]],
        resize_keyboard=True,
    )


@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "سلام! 👋\n"
        "با دکمه‌ی زیر نقشه‌کش Ladder را باز کنید، برنامه را طراحی کنید و با «📤 ارسال به ربات» "
        "برای من بفرستید تا پیش‌نمایش و کد Structured Text را دریافت کنید.",
        reply_markup=main_keyboard(),
    )


@dp.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "<b>راهنما</b>\n"
        "• <code>-| |-</code> کنتاکت باز (NO)\n"
        "• <code>-|/|-</code> کنتاکت بسته (NC)\n"
        "• <code>-( )-</code> کویل خروجی\n"
        "• <code>(S)</code> / <code>(R)</code> ست و ریست\n"
        "• <code>TON</code> تایمر روشن‌شدن با زمان PT (مثلاً 5s)\n"
        "• <code>CTU</code> شمارنده رو به بالا با مقدار PV\n\n"
        "هر ردیف باید در انتها یک خروجی داشته باشد. خانه‌های خالی به‌عنوان سیم در نظر گرفته می‌شوند.",
        reply_markup=main_keyboard(),
    )


@dp.message(F.web_app_data)
async def on_webapp_data(message: Message) -> None:
    raw = message.web_app_data.data
    try:
        rungs = parse_program(raw)
    except (ValueError, TypeError, AttributeError) as exc:
        await message.answer(f"❌ {html.escape(str(exc))}")
        return

    ladder = "\n".join(f"{i:>2}  {to_ladder(r)}" for i, r in enumerate(rungs, 1))
    st_code = to_structured_text(rungs)

    await message.answer(
        f"✅ برنامه دریافت شد ({len(rungs)} ردیف)\n<pre>{html.escape(ladder)}</pre>",
    )
    await message.answer_document(
        BufferedInputFile(st_code.encode("utf-8"), filename="program.st"),
        caption="کد Structured Text (IEC 61131-3)",
    )


async def main() -> None:
    if not BOT_TOKEN or not WEBAPP_URL:
        raise SystemExit("BOT_TOKEN و WEBAPP_URL را در فایل .env تنظیم کنید.")
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    logging.info("Bot is running...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
