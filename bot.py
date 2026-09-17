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
from aiogram.types import BotCommand, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("sb24gz_text")
router = Router()
MAX_TEXT_LENGTH = 3000


class TextState(StatesGroup):
    waiting_for_format = State()
    waiting_for_tool = State()
    waiting_for_organize = State()


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Create & Format", callback_data="format_text")],
        [InlineKeyboardButton(text="🔤 Text Tools", callback_data="text_tools")],
        [InlineKeyboardButton(text="📋 Copy / Organize", callback_data="copy_organize")],
        [InlineKeyboardButton(text="ℹ️ Help", callback_data="help")],
    ])


def tools_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="UPPERCASE", callback_data="tool_upper"), InlineKeyboardButton(text="lowercase", callback_data="tool_lower")],
        [InlineKeyboardButton(text="Word Count", callback_data="tool_words"), InlineKeyboardButton(text="Character Count", callback_data="tool_chars")],
        [InlineKeyboardButton(text="↩️ Main Menu", callback_data="main_menu")],
    ])


def back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ Main Menu", callback_data="main_menu")]])


def retry_menu(action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Try Again", callback_data=action)],
        [InlineKeyboardButton(text="↩️ Main Menu", callback_data="main_menu")],
    ])


WELCOME = (
    "<b>SB24GZ – អត្ថបទ</b>\n\n"
    "A simple Telegram-native text utility.\n\n"
    "✍️ <b>Create & Format</b> — clean and format text.\n"
    "🔤 <b>Text Tools</b> — change case and count words or characters.\n"
    "📋 <b>Copy / Organize</b> — clean spacing and organize text.\n\n"
    "All functions work directly inside Telegram."
)

HELP_TEXT = (
    "<b>SB24GZ – អត្ថបទ</b>\n\n"
    "Use this bot to work with text without leaving Telegram.\n\n"
    "1. Create & Format — clean spacing and blank lines.\n"
    "2. Text Tools — uppercase, lowercase, word count, character count.\n"
    "3. Copy / Organize — prepare readable text for reuse.\n\n"
    "Use /start for the main menu or /cancel to stop an operation."
)


def validate_text(text: str) -> str | None:
    value = (text or "").strip()
    if not value:
        return "Please send some text."
    if len(value) > MAX_TEXT_LENGTH:
        return f"That text is too long. Please keep it under {MAX_TEXT_LENGTH:,} characters."
    return None


def clean_text(text: str) -> str:
    lines = [re.sub(r"[ \\t]+", " ", line.strip()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def safe_text(text: str) -> str:
    return html.escape(text)


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(WELCOME, reply_markup=main_menu())


@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu())


@router.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Operation cancelled. Choose a function below.", reply_markup=main_menu())


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
    await state.set_state(TextState.waiting_for_format)
    if callback.message:
        await callback.message.edit_text(
            "<b>✍️ Create & Format</b>\n\n"
            "Send your text and the bot will clean extra spaces and blank lines.\n\n"
            f"Maximum: {MAX_TEXT_LENGTH:,} characters. Use /cancel to stop.",
            reply_markup=back_menu(),
        )


@router.message(TextState.waiting_for_format, F.text)
async def receive_format_text(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    error = validate_text(text)
    if error:
        await message.answer(error, reply_markup=retry_menu("format_text"))
        return
    result = clean_text(text)
    await state.clear()
    await message.answer("<b>✅ Formatted Text</b>\n\n" f"<blockquote>{safe_text(result)}</blockquote>", reply_markup=main_menu())


@router.message(TextState.waiting_for_format)
async def reject_non_text_format(message: Message) -> None:
    await message.answer("Please send a text message.", reply_markup=retry_menu("format_text"))


@router.callback_query(F.data == "text_tools")
async def text_tools_handler(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.edit_text("<b>🔤 Text Tools</b>\n\nChoose an operation, then send your text.", reply_markup=tools_menu())


async def start_tool(callback: CallbackQuery, state: FSMContext, tool: str, title: str) -> None:
    await callback.answer()
    await state.set_state(TextState.waiting_for_tool)
    await state.update_data(tool=tool, title=title)
    if callback.message:
        await callback.message.edit_text(
            f"<b>🔤 {safe_text(title)}</b>\n\n"
            f"Send the text to process. Maximum: {MAX_TEXT_LENGTH:,} characters. Use /cancel to stop.",
            reply_markup=back_menu(),
        )


@router.callback_query(F.data == "tool_upper")
async def tool_upper(callback: CallbackQuery, state: FSMContext) -> None:
    await start_tool(callback, state, "upper", "UPPERCASE")


@router.callback_query(F.data == "tool_lower")
async def tool_lower(callback: CallbackQuery, state: FSMContext) -> None:
    await start_tool(callback, state, "lower", "lowercase")


@router.callback_query(F.data == "tool_words")
async def tool_words(callback: CallbackQuery, state: FSMContext) -> None:
    await start_tool(callback, state, "words", "Word Count")


@router.callback_query(F.data == "tool_chars")
async def tool_chars(callback: CallbackQuery, state: FSMContext) -> None:
    await start_tool(callback, state, "chars", "Character Count")


@router.message(TextState.waiting_for_tool, F.text)
async def process_tool(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    error = validate_text(text)
    if error:
        await message.answer(error, reply_markup=retry_menu("text_tools"))
        return
    data = await state.get_data()
    tool = data.get("tool")
    if tool == "upper":
        response = f"<b>✅ Result</b>\n\n<blockquote>{safe_text(text.upper())}</blockquote>"
    elif tool == "lower":
        response = f"<b>✅ Result</b>\n\n<blockquote>{safe_text(text.lower())}</blockquote>"
    elif tool == "words":
        response = f"<b>✅ Word Count</b>\n\nWords: <b>{len(text.split())}</b>"
    elif tool == "chars":
        response = f"<b>✅ Character Count</b>\n\nCharacters: <b>{len(text)}</b>"
    else:
        await state.clear()
        await message.answer("That operation is unavailable. Please choose another function.", reply_markup=main_menu())
        return
    await state.clear()
    await message.answer(response, reply_markup=tools_menu())


@router.message(TextState.waiting_for_tool)
async def reject_non_text_tool(message: Message) -> None:
    await message.answer("Please send a text message.", reply_markup=retry_menu("text_tools"))


@router.callback_query(F.data == "copy_organize")
async def copy_organize_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(TextState.waiting_for_organize)
    if callback.message:
        await callback.message.edit_text(
            "<b>📋 Copy / Organize</b>\n\n"
            "Send text and the bot will remove extra spaces and blank lines.\n\n"
            f"Maximum: {MAX_TEXT_LENGTH:,} characters. Use /cancel to stop.",
            reply_markup=back_menu(),
        )


@router.message(TextState.waiting_for_organize, F.text)
async def receive_organized_text(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    error = validate_text(text)
    if error:
        await message.answer(error, reply_markup=retry_menu("copy_organize"))
        return
    result = clean_text(text)
    await state.clear()
    await message.answer("<b>✅ Organized Text</b>\n\n" f"<blockquote>{safe_text(result)}</blockquote>", reply_markup=main_menu())


@router.message(TextState.waiting_for_organize)
async def reject_non_text_organize(message: Message) -> None:
    await message.answer("Please send a text message.", reply_markup=retry_menu("copy_organize"))


async def configure_commands(bot: Bot) -> None:
    await bot.set_my_commands([
        BotCommand(command="start", description="Open the text utility"),
        BotCommand(command="help", description="Show available functions"),
        BotCommand(command="cancel", description="Cancel current operation"),
    ])


async def main() -> None:
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    logger.info("Starting SB24GZ text bot")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await configure_commands(bot)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("SB24GZ text bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
