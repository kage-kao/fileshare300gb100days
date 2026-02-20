"""
Telegram bot (aiogram 3) - GigaFile.nu helper
- GigaFile URL -> 3 types of links
- Any HTTP URL  -> re-upload to GigaFile -> 3 links
- File/document -> upload to GigaFile -> 3 links
- Inline keyboard buttons
- Multilingual (auto-detect from Telegram language_code)
- Quick commands
- /start does NOT cancel active operations
"""
import re
import logging
import time
import asyncio
import aiohttp
import tempfile
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    BotCommand,
)

from gigafile_client import gigafile_client
from i18n import get_lang, t, LANG_NAMES, SUPPORTED_LANGS

logger = logging.getLogger(__name__)

# Patterns
GIGAFILE_PAGE_RE = re.compile(
    r'https?://(\d+)\.gigafile\.nu/([0-9]{4}-[a-f0-9]{32,})',
    re.IGNORECASE,
)
GIGAFILE_DL_RE = re.compile(
    r'https?://(\d+)\.gigafile\.nu/download\.php\?file=([0-9]{4}-[a-f0-9]{32,})',
    re.IGNORECASE,
)
GIGAFILE_ANY_RE = re.compile(
    r'https?://(\d+)\.gigafile\.nu/',
    re.IGNORECASE,
)
URL_RE = re.compile(r'https?://\S+', re.IGNORECASE)

# Module-level objects
_proxy_base_url: str = ""
bot: Bot | None = None
dp = Dispatcher(storage=MemoryStorage())

# Track active tasks for cancellation
_active_tasks: dict[int, asyncio.Event] = {}

# User language preferences (in-memory, chat_id -> lang)
_user_langs: dict[int, str] = {}


class BotStates(StatesGroup):
    waiting_upload_settings = State()
    waiting_url_duration = State()


def _get_lang(message_or_cb) -> str:
    """Get language for user - from preferences or Telegram language_code."""
    chat_id = None
    lang_code = None
    if hasattr(message_or_cb, 'chat'):
        chat_id = message_or_cb.chat.id
    if hasattr(message_or_cb, 'message') and hasattr(message_or_cb.message, 'chat'):
        chat_id = message_or_cb.message.chat.id
    if hasattr(message_or_cb, 'from_user') and message_or_cb.from_user:
        lang_code = message_or_cb.from_user.language_code

    if chat_id and chat_id in _user_langs:
        return _user_langs[chat_id]
    return get_lang(lang_code)


def _esc(s: str) -> str:
    for ch in r'\_*[]()~`>#+-=|{}.!':
        s = s.replace(ch, '\\' + ch)
    return s


def _links_text(lang: str, page_url: str, direct_url: str, proxy_url: str, filename: str = "") -> str:
    fn_line = f"\n\n*{_esc(t(lang, 'file_label'))}* `{_esc(filename)}`" if filename else ""
    return (
        f"{_esc(t(lang, 'done'))}\n\n"
        f"*{_esc(t(lang, 'page_url'))}*\n"
        f"`{_esc(page_url)}`\n\n"
        f"*{_esc(t(lang, 'direct_url'))}*\n"
        f"`{_esc(direct_url)}`\n\n"
        f"*{_esc(t(lang, 'proxy_url'))}*\n"
        f"`{_esc(proxy_url)}`"
        f"{fn_line}"
    )


def _make_links(server_num: str, file_id: str) -> tuple[str, str, str]:
    page_url = f"https://{server_num}.gigafile.nu/{file_id}"
    direct_url = f"https://{server_num}.gigafile.nu/download.php?file={file_id}"
    proxy_url = f"{_proxy_base_url}/api/proxy?url={page_url}"
    return page_url, direct_url, proxy_url


def _links_keyboard(lang: str, page_url: str, proxy_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t(lang, "btn_open_page"), url=page_url),
            InlineKeyboardButton(text=t(lang, "btn_download_proxy"), url=proxy_url),
        ],
        [
            InlineKeyboardButton(text=t(lang, "btn_new_upload"), callback_data="new_upload"),
        ],
    ])


def _start_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t(lang, "btn_help"), callback_data="help"),
            InlineKeyboardButton(text=t(lang, "btn_language"), callback_data="lang_menu"),
        ],
    ])


def _duration_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t(lang, "dur_days", n=3), callback_data="dur_3"),
            InlineKeyboardButton(text=t(lang, "dur_days", n=5), callback_data="dur_5"),
            InlineKeyboardButton(text=t(lang, "dur_days", n=7), callback_data="dur_7"),
            InlineKeyboardButton(text=t(lang, "dur_days", n=14), callback_data="dur_14"),
        ],
        [
            InlineKeyboardButton(text=t(lang, "dur_days", n=30), callback_data="dur_30"),
            InlineKeyboardButton(text=t(lang, "dur_days", n=60), callback_data="dur_60"),
            InlineKeyboardButton(text=t(lang, "dur_days", n=100), callback_data="dur_100"),
        ],
    ])


def _lang_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for code, name in LANG_NAMES.items():
        row.append(InlineKeyboardButton(text=name, callback_data=f"setlang_{code}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _make_progress_cb(status_msg: Message, cancel_event: asyncio.Event, lang: str):
    last = {'stage': '', 'pct': -1, 'ts': 0.0}

    async def cb(stage: str, pct: int):
        if cancel_event.is_set():
            return
        now = time.monotonic()
        if stage == last['stage'] and pct == last['pct']:
            return
        # Throttle updates: min 2s between edits, except for 0% and 100%
        if now - last['ts'] < 2.0 and pct not in (0, 100):
            return
        last.update(stage=stage, pct=pct, ts=now)
        icon = t(lang, 'downloading') if stage == 'download' else t(lang, 'uploading')
        try:
            await status_msg.edit_text(f"{icon}: {pct}%")
        except Exception:
            pass

    return cb


def _is_gigafile_url(url: str) -> bool:
    return bool(GIGAFILE_ANY_RE.search(url))


def _is_own_proxy_url(url: str) -> bool:
    if not _proxy_base_url:
        return False
    return url.startswith(_proxy_base_url)


def _extract_gigafile_info(text: str) -> tuple[str, str] | None:
    dl_m = GIGAFILE_DL_RE.search(text)
    if dl_m:
        return dl_m.group(1), dl_m.group(2)

    page_m = GIGAFILE_PAGE_RE.search(text)
    if page_m:
        return page_m.group(1), page_m.group(2)

    return None


# ────────────────────── Handlers ──────────────────────

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    # BUG FIX: /start does NOT cancel active operations anymore.
    # Only /cancel should cancel operations.
    lang = _get_lang(message)
    await message.answer(
        f"*{_esc(t(lang, 'start_title'))}*\n\n"
        f"{_esc(t(lang, 'start_desc'))}\n\n"
        f"*{_esc(t(lang, 'start_gigafile'))}*\n"
        f"*{_esc(t(lang, 'start_url'))}*\n"
        f"*{_esc(t(lang, 'start_file'))}*\n\n"
        f"*{_esc(t(lang, 'help_commands'))}*\n"
        f"/help \\- {_esc(t(lang, 'btn_help'))}\n"
        f"/cancel \\- {_esc(t(lang, 'cancelled'))}\n"
        f"/lang \\- {_esc(t(lang, 'btn_language'))}\n",
        parse_mode="MarkdownV2",
        reply_markup=_start_keyboard(lang),
    )


@dp.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext):
    lang = _get_lang(message)
    await message.answer(
        f"*{_esc(t(lang, 'help_title'))}*\n\n"
        f"*{_esc(t(lang, 'help_gigafile'))}*\n"
        f"  {_esc(t(lang, 'help_gigafile_desc'))}\n\n"
        f"*{_esc(t(lang, 'help_url'))}*\n"
        f"  {_esc(t(lang, 'help_url_desc'))}\n"
        f"  `{_esc(t(lang, 'help_url_days'))}`\n\n"
        f"*{_esc(t(lang, 'help_file'))}*\n"
        f"  {_esc(t(lang, 'help_file_desc'))}\n\n"
        f"*{_esc(t(lang, 'help_commands'))}*\n"
        f"/start \\- {_esc(t(lang, 'start_title'))}\n"
        f"/help \\- {_esc(t(lang, 'btn_help'))}\n"
        f"/cancel \\- {_esc(t(lang, 'cancelled'))}\n"
        f"/lang \\- {_esc(t(lang, 'btn_language'))}\n",
        parse_mode="MarkdownV2",
        reply_markup=_start_keyboard(lang),
    )


@dp.message(Command("lang"))
async def cmd_lang(message: Message, state: FSMContext):
    lang = _get_lang(message)
    await message.answer(
        _esc(t(lang, 'choose_language')),
        parse_mode="MarkdownV2",
        reply_markup=_lang_keyboard(),
    )


@dp.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    lang = _get_lang(callback)
    await callback.message.answer(
        f"*{_esc(t(lang, 'help_title'))}*\n\n"
        f"*{_esc(t(lang, 'help_gigafile'))}*\n"
        f"  {_esc(t(lang, 'help_gigafile_desc'))}\n\n"
        f"*{_esc(t(lang, 'help_url'))}*\n"
        f"  {_esc(t(lang, 'help_url_desc'))}\n"
        f"  `{_esc(t(lang, 'help_url_days'))}`\n\n"
        f"*{_esc(t(lang, 'help_file'))}*\n"
        f"  {_esc(t(lang, 'help_file_desc'))}\n",
        parse_mode="MarkdownV2",
    )


@dp.callback_query(F.data == "lang_menu")
async def cb_lang_menu(callback: CallbackQuery):
    await callback.answer()
    lang = _get_lang(callback)
    await callback.message.answer(
        _esc(t(lang, 'choose_language')),
        parse_mode="MarkdownV2",
        reply_markup=_lang_keyboard(),
    )


@dp.callback_query(F.data.startswith("setlang_"))
async def cb_set_lang(callback: CallbackQuery):
    await callback.answer()
    new_lang = callback.data.split("_", 1)[1]
    chat_id = callback.message.chat.id
    if new_lang in SUPPORTED_LANGS:
        _user_langs[chat_id] = new_lang
    lang = new_lang if new_lang in SUPPORTED_LANGS else "en"
    await callback.message.edit_text(
        _esc(t(lang, 'lang_changed')),
        parse_mode="MarkdownV2",
        reply_markup=_start_keyboard(lang),
    )


@dp.callback_query(F.data == "new_upload")
async def cb_new_upload(callback: CallbackQuery):
    await callback.answer()
    lang = _get_lang(callback)
    await callback.message.answer(
        _esc(t(lang, 'send_link_or_file')),
        parse_mode="MarkdownV2",
    )


@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    lang = _get_lang(message)
    chat_id = message.chat.id
    cancelled = False

    if chat_id in _active_tasks:
        _active_tasks[chat_id].set()
        del _active_tasks[chat_id]
        cancelled = True

    current_state = await state.get_state()
    if current_state:
        await state.clear()
        cancelled = True

    if cancelled:
        await message.answer(_esc(t(lang, 'cancelled')), parse_mode="MarkdownV2")
    else:
        await message.answer(_esc(t(lang, 'no_active')), parse_mode="MarkdownV2")


# Duration callback - handles both file uploads and URL uploads
@dp.callback_query(F.data.startswith("dur_"))
async def cb_duration(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    duration = int(callback.data.split("_")[1])
    data = await state.get_data()
    await state.clear()
    lang = _get_lang(callback)
    chat_id = callback.message.chat.id

    # Check if this is a URL upload
    pending_url = data.get('pending_url')
    if pending_url:
        cancel_event = asyncio.Event()
        _active_tasks[chat_id] = cancel_event

        status_msg = await callback.message.edit_text(t(lang, 'init'))
        try:
            cb = _make_progress_cb(status_msg, cancel_event, lang)
            result = await gigafile_client.upload_from_url(
                pending_url, lifetime=duration,
                progress_cb=cb, cancel_event=cancel_event,
            )

            if cancel_event.is_set():
                await status_msg.edit_text(t(lang, 'cancelled'))
                return

            if result.get('success'):
                proxy_url = f"{_proxy_base_url}/api/proxy?url={result['page_url']}"
                kb = _links_keyboard(lang, result['page_url'], proxy_url)
                await status_msg.edit_text(
                    _links_text(lang, result['page_url'], result['direct_url'], proxy_url, result.get('filename', '')),
                    parse_mode="MarkdownV2",
                    reply_markup=kb,
                )
            else:
                await status_msg.edit_text(f"{t(lang, 'error')} {result.get('error', t(lang, 'unknown_error'))}")
        except Exception as e:
            logger.exception("upload_from_url failed for %s", pending_url)
            await status_msg.edit_text(f"{t(lang, 'error')} {str(e)[:300]}")
        finally:
            _active_tasks.pop(chat_id, None)
        return

    # File upload path
    file_path = data.get('file_path')
    file_name = data.get('file_name', 'file')

    if not file_path or not os.path.exists(file_path):
        await callback.message.edit_text(t(lang, 'file_not_found'))
        return

    cancel_event = asyncio.Event()
    _active_tasks[chat_id] = cancel_event

    status_msg = await callback.message.edit_text(t(lang, 'uploading_duration', dur=duration))

    try:
        cb = _make_progress_cb(status_msg, cancel_event, lang)
        result = await gigafile_client.upload_file_path(
            file_path, lifetime=duration, progress_cb=cb
        )

        if cancel_event.is_set():
            await status_msg.edit_text(t(lang, 'cancelled'))
            return

        if result.get('success'):
            proxy_url = f"{_proxy_base_url}/api/proxy?url={result['page_url']}"
            text = _links_text(lang, result['page_url'], result['direct_url'], proxy_url, filename=file_name)
            kb = _links_keyboard(lang, result['page_url'], proxy_url)
            await status_msg.edit_text(text, parse_mode="MarkdownV2", reply_markup=kb)
        else:
            await status_msg.edit_text(f"{t(lang, 'error')} {result.get('error', t(lang, 'unknown_error'))}")
    except Exception as e:
        logger.exception("File upload failed")
        await status_msg.edit_text(f"{t(lang, 'error')} {str(e)[:300]}")
    finally:
        _active_tasks.pop(chat_id, None)
        if file_path and os.path.exists(file_path):
            try:
                os.unlink(file_path)
            except Exception:
                pass


# Handle files/documents
@dp.message(F.document)
async def handle_document(message: Message, state: FSMContext):
    await state.clear()
    lang = _get_lang(message)
    doc = message.document
    file_name = doc.file_name or 'file'
    file_size_mb = (doc.file_size or 0) / (1024 * 1024)

    if file_size_mb > 20:
        await message.answer(
            _esc(t(lang, 'file_too_big', size=f"{file_size_mb:.1f}")),
            parse_mode="MarkdownV2",
        )
        return

    status_msg = await message.answer(t(lang, 'receiving_file'))
    try:
        file_info = await bot.get_file(doc.file_id)
        tmp_path = tempfile.mktemp(suffix=f"_{file_name}")
        await bot.download_file(file_info.file_path, tmp_path)

        await state.set_state(BotStates.waiting_upload_settings)
        await state.update_data(file_path=tmp_path, file_name=file_name)
        await status_msg.edit_text(
            f"*{_esc(t(lang, 'file_info', name=file_name, size=f'{file_size_mb:.1f}'))}*\n\n{_esc(t(lang, 'choose_duration'))}",
            parse_mode="MarkdownV2",
            reply_markup=_duration_keyboard(lang),
        )
    except Exception as e:
        logger.exception("Failed to download file from Telegram")
        await status_msg.edit_text(f"{t(lang, 'error')} {str(e)[:200]}")


# Handle photos
@dp.message(F.photo)
async def handle_photo(message: Message, state: FSMContext):
    await state.clear()
    lang = _get_lang(message)
    photo = message.photo[-1]
    file_size_mb = (photo.file_size or 0) / (1024 * 1024)

    status_msg = await message.answer(t(lang, 'receiving_file'))
    try:
        file_info = await bot.get_file(photo.file_id)
        file_name = f"photo_{photo.file_unique_id}.jpg"
        tmp_path = tempfile.mktemp(suffix=f"_{file_name}")
        await bot.download_file(file_info.file_path, tmp_path)

        await state.set_state(BotStates.waiting_upload_settings)
        await state.update_data(file_path=tmp_path, file_name=file_name)
        await status_msg.edit_text(
            f"*{_esc(t(lang, 'file_info', name=file_name, size=f'{file_size_mb:.1f}'))}*\n\n{_esc(t(lang, 'choose_duration'))}",
            parse_mode="MarkdownV2",
            reply_markup=_duration_keyboard(lang),
        )
    except Exception as e:
        logger.exception("Failed to download photo from Telegram")
        await status_msg.edit_text(f"{t(lang, 'error')} {str(e)[:200]}")


# Handle video
@dp.message(F.video)
async def handle_video(message: Message, state: FSMContext):
    await state.clear()
    lang = _get_lang(message)
    video = message.video
    file_name = video.file_name or f"video_{video.file_unique_id}.mp4"
    file_size_mb = (video.file_size or 0) / (1024 * 1024)

    if file_size_mb > 20:
        await message.answer(
            _esc(t(lang, 'file_too_big', size=f"{file_size_mb:.1f}")),
            parse_mode="MarkdownV2",
        )
        return

    status_msg = await message.answer(t(lang, 'receiving_file'))
    try:
        file_info = await bot.get_file(video.file_id)
        tmp_path = tempfile.mktemp(suffix=f"_{file_name}")
        await bot.download_file(file_info.file_path, tmp_path)

        await state.set_state(BotStates.waiting_upload_settings)
        await state.update_data(file_path=tmp_path, file_name=file_name)
        await status_msg.edit_text(
            f"*{_esc(t(lang, 'file_info', name=file_name, size=f'{file_size_mb:.1f}'))}*\n\n{_esc(t(lang, 'choose_duration'))}",
            parse_mode="MarkdownV2",
            reply_markup=_duration_keyboard(lang),
        )
    except Exception as e:
        logger.exception("Failed to download video from Telegram")
        await status_msg.edit_text(f"{t(lang, 'error')} {str(e)[:200]}")


@dp.message(F.text)
async def handle_text(message: Message, state: FSMContext):
    # Don't clear state if there's an active upload task - let FSM handle duration selection
    lang = _get_lang(message)
    text = message.text.strip()

    url_m = URL_RE.search(text)
    if url_m:
        found_url = url_m.group(0)
        if _is_own_proxy_url(found_url):
            gf_info = _extract_gigafile_info(found_url)
            if gf_info:
                server_num, file_id = gf_info
                page_url, direct_url, proxy_url = _make_links(server_num, file_id)
                kb = _links_keyboard(lang, page_url, proxy_url)
                await message.answer(
                    _links_text(lang, page_url, direct_url, proxy_url),
                    parse_mode="MarkdownV2",
                    reply_markup=kb,
                )
                return
            else:
                await message.answer(
                    _esc(t(lang, 'gigafile_bad_link')),
                    parse_mode="MarkdownV2",
                )
                return

    gf_info = _extract_gigafile_info(text)

    if gf_info:
        server_num, file_id = gf_info
        page_url, direct_url, proxy_url = _make_links(server_num, file_id)
        kb = _links_keyboard(lang, page_url, proxy_url)
        await message.answer(
            _links_text(lang, page_url, direct_url, proxy_url),
            parse_mode="MarkdownV2",
            reply_markup=kb,
        )
        return

    if url_m:
        found_url = url_m.group(0)

        if _is_gigafile_url(found_url):
            await message.answer(
                _esc(t(lang, 'gigafile_bad_link')),
                parse_mode="MarkdownV2",
            )
            return

        # Check for explicit days=N in text
        explicit_duration = None
        for tok in text[url_m.end():].split():
            if tok.startswith('days='):
                try:
                    d = int(tok[5:])
                    if d in {3, 5, 7, 14, 30, 60, 100}:
                        explicit_duration = d
                except ValueError:
                    pass

        chat_id = message.chat.id

        # Prevent duplicate uploads - if already uploading, ignore
        if chat_id in _active_tasks and not _active_tasks[chat_id].is_set():
            return

        # If days=N specified explicitly, start immediately
        if explicit_duration:
            cancel_event = asyncio.Event()
            _active_tasks[chat_id] = cancel_event

            status_msg = await message.answer(t(lang, 'init'))
            try:
                cb = _make_progress_cb(status_msg, cancel_event, lang)
                result = await gigafile_client.upload_from_url(
                    found_url, lifetime=explicit_duration,
                    progress_cb=cb, cancel_event=cancel_event,
                )

                if cancel_event.is_set():
                    await status_msg.edit_text(t(lang, 'cancelled'))
                    return

                if result.get('success'):
                    proxy_url = f"{_proxy_base_url}/api/proxy?url={result['page_url']}"
                    kb = _links_keyboard(lang, result['page_url'], proxy_url)
                    await status_msg.edit_text(
                        _links_text(lang, result['page_url'], result['direct_url'], proxy_url, result.get('filename', '')),
                        parse_mode="MarkdownV2",
                        reply_markup=kb,
                    )
                else:
                    await status_msg.edit_text(f"{t(lang, 'error')} {result.get('error', t(lang, 'unknown_error'))}")
            except Exception as e:
                logger.exception("upload_from_url failed for %s", found_url)
                await status_msg.edit_text(f"{t(lang, 'error')} {str(e)[:300]}")
            finally:
                _active_tasks.pop(chat_id, None)
            return

        # No explicit duration - show duration keyboard
        await state.set_state(BotStates.waiting_url_duration)
        await state.update_data(pending_url=found_url)
        await message.answer(
            f"*{_esc(t(lang, 'help_url'))}*\n`{_esc(found_url[:100])}`\n\n{_esc(t(lang, 'choose_duration'))}",
            parse_mode="MarkdownV2",
            reply_markup=_duration_keyboard(lang),
        )
        return

    await message.answer(
        _esc(t(lang, 'send_link_or_file')),
        parse_mode="MarkdownV2",
    )


# Lifecycle

async def setup_webhook(token: str, webhook_url: str, proxy_base: str):
    global bot, _proxy_base_url
    _proxy_base_url = proxy_base
    bot = Bot(token=token)

    # Set bot commands for quick access
    commands = [
        BotCommand(command="start", description="Start the bot"),
        BotCommand(command="help", description="Show help"),
        BotCommand(command="cancel", description="Cancel current operation"),
        BotCommand(command="lang", description="Change language"),
    ]
    try:
        await bot.set_my_commands(commands)
        logger.info("Bot commands set successfully")
    except Exception as e:
        logger.warning("Failed to set bot commands: %s", e)

    await bot.set_webhook(
        url=webhook_url,
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"],
    )
    logger.info("Webhook set to %s", webhook_url)


async def teardown_webhook():
    if bot:
        await bot.delete_webhook()
        await bot.session.close()
        logger.info("Webhook removed")
