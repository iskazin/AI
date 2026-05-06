"""
handlers/onboarding.py
Диагностический диалог — 5 фаз, базовые рекомендации, загрузка документов
"""
import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from states.states import OnboardingStates
from database.db import create_consultation, update_consultation_phase

router = Router()

CHANNEL_LINK = "https://t.me/dr_iskazin"
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))


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


def after_docs_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Всё загружено, продолжить", callback_data="docs_done")
    builder.button(text="⏭ Пропустить", callback_data="docs_done")
    builder.button(text="🏠 В главное меню", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()


@router.callback_query(F.data == "start_consultation")
async def start_consultation(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    consultation_id = await create_consultation(callback.from_user.id)
    await state.update_data(consultation_id=consultation_id, docs=[])
    await callback.message.edit_text(
        "📋 <b>Диагностический протокол Neo Clinic</b>\n\n"
        "Мы проведём структурированный сбор анамнеза в несколько этапов.\n\n"
        "<b>Этап 1 из 5:</b> Основная жалоба\n\n"
        "Что вас беспокоит? Опишите своими словами — без ограничений.",
        parse_mode="HTML",
        reply_markup=back_to_menu_kb()
    )
    await state.set_state(OnboardingStates.phase2_complaints)
    await callback.answer()


@router.message(OnboardingStates.phase2_complaints)
async def phase2(message: Message, state: FSMContext):
    data = await state.get_data()
    await update_consultation_phase(data.get("consultation_id", 0), "phase2_complaints", message.text or "")
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 В главное меню", callback_data="back_to_menu")
    await message.answer(
        "Принято.\n\n"
        "<b>Этап 2 из 5:</b> История\n\n"
        "Когда это началось? Как развивалось? Что предшествовало текущему состоянию?",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await state.set_state(OnboardingStates.phase3_history)


@router.message(OnboardingStates.phase3_history)
async def phase3(message: Message, state: FSMContext):
    data = await state.get_data()
    await update_consultation_phase(data.get("consultation_id", 0), "phase3_history", message.text or "")
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 В главное меню", callback_data="back_to_menu")
    await message.answer(
        "<b>Этап 3 из 5:</b> Уточняющие данные\n\n"
        "1. Возраст и пол\n"
        "2. Рост и вес\n"
        "3. Хронические заболевания (если есть)\n"
        "4. Препараты или добавки\n"
        "5. Уровень физической активности (низкий / средний / высокий)\n\n"
        "Можно отвечать в свободной форме.",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await state.set_state(OnboardingStates.phase4_followup)


@router.message(OnboardingStates.phase4_followup)
async def phase4(message: Message, state: FSMContext):
    data = await state.get_data()
    await update_consultation_phase(data.get("consultation_id", 0), "phase4_followup", message.text or "")
    await message.answer(
        "<b>Этап 4 из 5:</b> Документы и анализы\n\n"
        "Если есть результаты анализов, выписки или медицинские документы — "
        "отправьте их сейчас (фото или PDF).\n\n"
        "Можно отправить несколько файлов по одному.",
        parse_mode="HTML",
        reply_markup=after_docs_kb()
    )
    await state.set_state(OnboardingStates.phase5_docs)


@router.message(OnboardingStates.phase5_docs, F.document)
async def receive_document(message: Message, state: FSMContext):
    data = await state.get_data()
    docs = data.get("docs", [])
    docs.append({"type": "document", "file_id": message.document.file_id, "name": message.document.file_name or "документ"})
    await state.update_data(docs=docs)
    if ADMIN_ID:
        user = message.from_user
        await message.bot.send_document(
            chat_id=ADMIN_ID,
            document=message.document.file_id,
            caption=f"📄 Документ от пациента: {user.full_name or user.username}\n@{user.username or 'нет'}"
        )
    await message.answer(
        f"✅ Документ получен ({message.document.file_name or 'файл'}).\nМожете отправить ещё или нажмите «Всё загружено».",
        reply_markup=after_docs_kb()
    )


@router.message(OnboardingStates.phase5_docs, F.photo)
async def receive_photo_doc(message: Message, state: FSMContext):
    data = await state.get_data()
    docs = data.get("docs", [])
    photo = message.photo[-1]
    docs.append({"type": "photo", "file_id": photo.file_id})
    await state.update_data(docs=docs)
    if ADMIN_ID:
        user = message.from_user
        await message.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo.file_id,
            caption=f"🖼 Фото документа от: {user.full_name or user.username}\n@{user.username or 'нет'}"
        )
    await message.answer(
        "✅ Фото получено.\nМожете отправить ещё или нажмите «Всё загружено».",
        reply_markup=after_docs_kb()
    )


@router.callback_query(F.data == "docs_done")
async def docs_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    consultation_id = data.get("consultation_id", 0)
    docs_count = len(data.get("docs", []))
    await update_consultation_phase(consultation_id, "status", "completed")

    recs = (
        "<b>Этап 5 из 5: Базовый протокол здоровья</b>\n\n"
        "Пока доктор готовит персональное заключение — фундаментальные принципы Medicine 3.0:\n\n"
        "😴 <b>Сон</b>\n"
        "7–9 часов. Ложитесь до 23:00. За час до сна — никакого синего света. "
        "Температура в спальне 18–20°C.\n\n"
        "🥗 <b>Питание</b>\n"
        "Основа — белок + некрахмалистые овощи + здоровые жиры. "
        "Минимизируйте ультрапереработанные продукты и сахар. "
        "Последний приём пищи — за 3 часа до сна.\n\n"
        "💧 <b>Вода</b>\n"
        "30–35 мл на кг веса в день. Стакан воды сразу после пробуждения. "
        "Чай и кофе не считаются.\n\n"
        "🏃 <b>Физическая активность</b>\n"
        "150 минут умеренной нагрузки в неделю. "
        "Силовые тренировки 2–3 раза. "
        "10 000 шагов в день как базовый ориентир.\n\n"
        "Это фундамент. Персональные рекомендации — после анализа ваших данных доктором."
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Записаться на сессию", url="https://t.me/AibatyrIskazin_bot")
    builder.button(text="🏠 В главное меню", callback_data="back_to_menu")
    builder.adjust(1)

    await callback.message.edit_text(recs, parse_mode="HTML", reply_markup=builder.as_markup())

    if ADMIN_ID:
        user = callback.from_user
        name = user.full_name or user.username or str(user.id)
        username = f"@{user.username}" if user.username else "нет username"
        await callback.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"🔔 <b>Новая консультация завершена</b>\n\n"
                f"Пациент: {name} ({username})\n"
                f"ID: <code>{user.id}</code>\n"
                f"Документов: {docs_count}\n\n"
                f"/admin → Пациенты → карточка для просмотра ответов."
            ),
            parse_mode="HTML"
        )

    await callback.bot.send_message(
        chat_id=callback.from_user.id,
        text=(
            "Пока готовится ваше заключение — присоединяйтесь к каналу доктора.\n\n"
            "Мысли о здоровье и долголетии, живые эфиры, утренние практики и медитации.\n"
            "Не просто канал — среда, которая меняет качество жизни."
        ),
        reply_markup=channel_kb()
    )

    await state.clear()
    await callback.answer()
