"""
handlers/common.py
Базовые команды: /start, /help, возврат в меню
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from keyboards.keyboards import main_menu
from database.db import get_or_create_patient

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await get_or_create_patient(
        telegram_id=message.from_user.id,
        username=message.from_user.username or "",
        full_name=message.from_user.full_name or ""
    )
    await message.answer(
        f"Добрый день, {message.from_user.first_name}.\n\n"
        "Вы в Neo Clinic — отделение превентивной медицины и долголетия.\n\n"
        "Здесь работает принцип Медицины 3.0: не лечить болезнь, а предупреждать её. "
        "Долголетие — это система, а не случайность.\n\n"
        "Выберите, с чего начнём:",
        reply_markup=main_menu()
    )


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Главное меню Neo Clinic:",
        reply_markup=main_menu()
    )
    await callback.answer()


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Neo Clinic Bot\n\n"
        "/start — Главное меню\n"
        "/admin — Панель администратора (только для доктора)\n\n"
        "По вопросам: t.me/AibatyrIskazin_bot"
    )
