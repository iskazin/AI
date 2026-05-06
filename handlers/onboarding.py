"""
handlers/onboarding.py
Диагностический диалог — 5 фаз, все ответы сохраняются в БД
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from states.states import OnboardingStates
from database.db import create_consultation, update_consultation_phase, get_or_create_patient
from keyboards.keyboards import main_menu

router = Router()

CHANNEL_LINK = "https://t.me/dr_iskazin"


def back_to_menu_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 В главное меню", callback_data="back_to_menu")
    return builder.as_markup()


def channel_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="📱 Перейти в канал", url=CHANNEL_LINK)
    builder.button(text="🏠 В главное меню", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()


# ─── Старт консультации ────────────────────────────────────────────────────

@router.callback_query(F.data == "start_consultation")
async def start_consultation(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    # Создаём новую консультацию в БД
    consultation_id = await create_consultation(callback.from_user.id)
    await state.update_data(consultation_id=consultation_id)

    await callback.message.edit_text(
        "📋 <b>Диагностический протокол Neo Clinic</b>\n\n"
        "Мы проведём структурированный сбор анамнеза в несколько этапов.\n\n"
        "<b>Этап 1 из 4:</b> Опишите вашу основную жалобу.\n\n"
        "Что вас беспокоит? Опишите своими словами — без ограничений.",
        parse_mode="HTML",
        reply_markup=back_to_menu_kb()
    )
    await state.set_state(OnboardingStates.phase2_complaints)
    await callback.answer()


# ─── Фаза 2: Жалобы ────────────────────────────────────────────────────────

@router.message(OnboardingStates.phase2_complaints)
async def phase2(message: Message, state: FSMContext):
    data = await state.get_data()
    consultation_id = data.get("consultation_id", 0)

    await update_consultation_phase(consultation_id, "phase2_complaints", message.text)

    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 В главное меню", callback_data="back_to_menu")

    await message.answer(
        "Принято.\n\n"
        "<b>Этап 2 из 4:</b> История\n\n"
        "Расскажите — когда это началось? Как развивалось? "
        "Что предшествовало текущему состоянию?",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await state.set_state(OnboardingStates.phase3_history)


# ─── Фаза 3: История ───────────────────────────────────────────────────────

@router.message(OnboardingStates.phase3_history)
async def phase3(message: Message, state: FSMContext):
    data = await state.get_data()
    consultation_id = data.get("consultation_id", 0)

    await update_consultation_phase(consultation_id, "phase3_history", message.text)

    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 В главное меню", callback_data="back_to_menu")

    await message.answer(
        "<b>Этап 3 из 4:</b> Уточняющие вопросы\n\n"
        "Ответьте на несколько пунктов:\n\n"
        "1. Ваш возраст и пол\n"
        "2. Рост и вес\n"
        "3. Хронические заболевания (если есть)\n"
        "4. Принимаете ли какие-то препараты или добавки?\n"
        "5. Уровень физической активности (низкий / средний / высокий)\n\n"
        "Можно отвечать в свободной форме.",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await state.set_state(OnboardingStates.phase4_followup)


# ─── Фаза 4: Уточняющие вопросы ───────────────────────────────────────────

@router.message(OnboardingStates.phase4_followup)
async def phase4(message: Message, state: FSMContext):
    data = await state.get_data()
    consultation_id = data.get("consultation_id", 0)

    await update_consultation_phase(consultation_id, "phase4_followup", message.text)

    # Финальное сообщение — заключение
    result_text = (
        "Анализирую данные...\n\n"
        "Ваши ответы получены и переданы доктору Айбатыру Исказину.\n\n"
        "В течение 24 часов вы получите персональное заключение "
        "с рекомендациями в рамках протокола Medicine 3.0.\n\n"
        "Если хотите ускорить процесс — запишитесь на личную стратегическую сессию."
    )

    await update_consultation_phase(consultation_id, "status", "completed")

    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Записаться на сессию", url="https://t.me/AibatyrIskazin_bot")
    builder.button(text="🏠 В главное меню", callback_data="back_to_menu")
    builder.adjust(1)

    await message.answer(result_text, reply_markup=builder.as_markup())

    # Приглашение в канал
    await message.answer(
        "Пока готовится ваше заключение — присоединяйтесь к каналу доктора.\n\n"
        "Там: мысли о здоровье и долголетии, живые эфиры, утренние практики и медитации.\n"
        "Не просто канал — среда, которая меняет качество жизни.",
        reply_markup=channel_kb()
    )

    await state.clear()
