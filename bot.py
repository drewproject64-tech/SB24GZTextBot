import asyncio
import html
import logging
import os
import re

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("sb24gz_text")
router = Router()
MAX_TEXT_LENGTH = 3000


class TextState(StatesGroup):
    waiting_for_text = State()
    waiting_for_saved_text = State()


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✍️ Create & Format", callback_data="format_text")],
            [InlineKeyboardButton(text="🔤 Text Tools", callback_data="text_tools")],
            [InlineKeyboardButton(text="📋 Copy / Organize", callback_data="copy_organize")],
            [InlineKeyboardButton(text="ℹ️ Help", callback_data="help")],
        ]
    )


def tools_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="UPPERCASE", callback_data="tool_upper"),
                InlineKeyboardButton(text="lowercase", callback_data="tool_lower"),
            ],
            [
                InlineKeyboardButton(text="Word Count", callback_data="tool_words"),
                InlineKeyboardButton(text="Character Count", callback_data="tool_chars"),
            ],
            [InlineKeyboardButton(text="↩️ Main Menu", callback_data="main_menu")],
        ]
    )


def back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="↩️ Main Menu", callback_data="main_menu")]]
    )


def text_retry_menu(action: str = "format_text") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Try Again", callback_data=action)],
            [InlineKeyboardButton(text="↩️ Main Menu", callback_data="main_menu")],
        ]
    )


WELCOME = (
    "<b>SB24GZ – អត្ថបទ</b>\n\n"
    "Create, format, copy, and organize text directly inside Telegram.\n\n"
    "✍️ <b>Create & Format</b> — clean and format text.\n"
    "🔤 <b>Text Tools</b> — count and transform text.\n"
    "📋 <b>Copy / Organize</b> — clean spacing and prepare text for reuse.\n\n"
    "Everything runs inside Telegram. Choose a function below."
)

HELP_TEXT = (
    "<b>SB24GZ – អត្ថបទ</b>\n\n"
    "A focused Telegram-native text utility.\n\n"
    "✍️ Create & Format: send text and receive a cleaned, readable version.\n"
    "🔤 Text Tools: use uppercase, lowercase, word count, and character count.\n"
    "📋 Copy / Organize: clean spacing and organize text for easy copying.\n\n"
    "Use /start anytime to return to the main menu."
)


def validate_text(text: str) -> str | None:
    value = (text or "").strip()
    if not value:
        return "Please send some text."
    if len(value) > MAX_TEXT_LENGTH:
        return f"That text is too long. Please keep it under {MAX_TEXT_LENGTH:,} characters."
    return None


def clean_text(text: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line.strip()) for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def safe_blockquote(text: str) -> str:
    return html.escape(text).replace("\n", "\n")


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(WELCOME, reply_markup=main_menu())


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu())


@router.callback_query(F.data == "main_menu")
async def main_menu_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(WELCOME, reply_markup=main_menu())


@router.callback_query(F.data == "help")
async def help_callback(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(HELP_TEXT, reply_markup=back_menu())


@router.callback_query(F.data == "format_text")
async def format_text_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(TextState.waiting_for_text)
    if callback.message:
        await callback.message.edit_text(
            "<b>✍️ Create & Format</b>\n\n"
            "Send your text. The bot will clean extra spacing and return a readable version.\n\n"
            f"Maximum: {MAX_TEXT_LENGTH:,} characters. Send /start to cancel.",
            reply_markup=back_menu(),
        )


@router.message(TextState.waiting_for_text, F.text)
async def receive_format_text(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    error = validate_text(text)
    if error:
        await message.answer(error, reply_markup=text_retry_menu("format_text"))
        return

    result = clean_text(text)
    await state.clear()
    await message.answer(
        "<b>✅ Formatted Text</b>\n\n"
        f"<blockquote>{safe_blockquote(result)}</blockquote>",
        reply_markup=main_menu(),
    )


@router.message(TextState.waiting_for_text)
async def reject_non_text(message: Message) -> None:
    await message.answer(
        "Please send a text message.",
        reply_markup=text_retry_menu("format_text"),
    )


@router.callback_query(F.data == "text_tools")
async def text_tools_handler(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(
            "<b>🔤 Text Tools</b>\n\n"
            "Choose an operation. You will then be asked for your text.",
            reply_markup=tools_menu(),
        )


async def run_tool(callback: CallbackQuery, state: FSMContext, tool: str, title: str) -> None:
    await callback.answer()
    await state.set_state(TextState.waiting_for_text)
    await state.update_data(tool=tool, title=title)
    if callback.message:
        await callback.message.edit_text(
            f"<b>🔤 {html.escape(title)}</b>\n\n"
            "Send the text to process.\n\n"
            f"Maximum: {MAX_TEXT_LENGTH:,} characters. Send /start to cancel.",
            reply_markup=back_menu(),
        )


@router.callback_query(F.data == "tool_upper")
async def tool_upper(callback: CallbackQuery, state: FSMContext) -> None:
    await run_tool(callback, state, "upper", "UPPERCASE")


@router.callback_query(F.data == "tool_lower")
async def tool_lower(callback: CallbackQuery, state: FSMContext) -> None:
    await run_tool(callback, state, "lower", "lowercase")


@router.callback_query(F.data == "tool_words")
async def tool_words(callback: CallbackQuery, state: FSMContext) -> None:
    await run_tool(callback, state, "words", "Word Count")


@router.callback_query(F.data == "tool_chars")
async def tool_chars(callback: CallbackQuery, state: FSMContext) -> None:
    await run_tool(callback, state, "chars", "Character Count")


@router.message(TextState.waiting_for_text, F.text)
async def process_tool_or_format(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    tool = data.get("tool")
    if not tool:
        return

    text = message.text or ""
    error = validate_text(text)
    if error:
        await message.answer(error, reply_markup=text_retry_menu("text_tools"))
        return

    if tool == "upper":
        result = text.upper()
    elif tool == "lower":
        result = text.lower()
    elif tool == "words":
        result = f"Word count: <b>{len(text.split())}</b>"
    elif tool == "chars":
        result = f"Character count: <b>{len(text)}</b>"
    else:
        await state.clear()
        await message.answer("That text operation is unavailable.", reply_markup=main_menu())
        return

    await state.clear()
    if tool in {"upper", "lower"}:
        result = html.escape(result)
        await message.answer(
            f"<b>✅ Result</b>\n\n<blockquote>{result}</blockquote>",
            reply_markup=tools_menu(),
        )
    else:
        await message.answer(f"<b>✅ Result</b>\n\n{result}", reply_markup=tools_menu())


@router.callback_query(F.data == "copy_organize")
async def copy_organize_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(TextState.waiting_for_saved_text)
    if callback.message:
        await callback.message.edit_text(
            "<b>📋 Copy / Organize</b>\n\n"
            "Send text and the bot will remove extra spaces and blank lines, making it easier to copy and reuse.\n\n"
            f"Maximum: {MAX_TEXT_LENGTH:,} characters.",
            reply_markup=back_menu(),
        )


@router.message(TextState.waiting_for_saved_text, F.text)
async def receive_organized_text(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    error = validate_text(text)
    if error:
        await message.answer(error, reply_markup=text_retry_menu("copy_organize"))
        return

    result = clean_text(text)
    await state.clear()
    await message.answer(
        "<b>✅ Organized Text</b>\n\n"
        f"<blockquote>{safe_blockquote(result)}</blockquote>",
        reply_markup=main_menu(),
    )


@router.message(TextState.waiting_for_saved_text)
async def reject_non_text_organized(message: Message) -> None:
    await message.answer(
        "Please send a text message.",
        reply_markup=text_retry_menu("copy_organize"),
    )


@router.callback_query(F.data == "create_post")
async def legacy_create_post(callback: CallbackQuery) -> None:
    await callback.answer("This function is not available.", show_alert=True)


async def main() -> None:
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)
    logger.info("Starting SB24GZ text bot")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("SB24GZ text bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
