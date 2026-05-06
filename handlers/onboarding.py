"""
handlers/onboarding.py
"""
import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from states.states import OnboardingStates, PaymentStates
from database.db import create_consultation, update_consultation_phase, create_payment, attach_receipt, save_document

router = Router()

CHANNEL_LINK = "https://t.me/dr_iskazin"
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
KASPI_PHONE = os.getenv("KASPI_PHONE", "+77771080196")
KASPI_NAME = os.getenv("KASPI_NAME", "Айбатыр Исказин")
CONSULTATION_PRICE = 15000

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
        "Структурированный сбор анамнеза в несколько этапов.\n\n"
        "<b>Этап 1 из 4:</b> Основная жалоба\n\n"
        "Что вас беспокоит? Опишите своими словами — без ограничений.",
        parse_mode="HTML", reply_markup=back_to_menu_kb()
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
        "Принято.\n\n<b>Этап 2 из 4:</b> История\n\n"
        "Когда это началось? Как развивалось? Что предшествовало текущему состоянию?",
        parse_mode="HTML", reply_markup=builder.as_markup()
    )
    await state.set_state(OnboardingStates.phase3_history)

@router.message(OnboardingStates.phase3_history)
async def phase3(message: Message, state: FSMContext):
    data = await state.get_data()
    await update_consultation_phase(data.get("consultation_id", 0), "phase3_history", message.text or "")
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 В главное меню", callback_data="back_to_menu")
    await message.answer(
        "<b>Этап 3 из 4:</b> Уточняющие данные\n\n"
        "1. Возраст и пол\n2. Рост и вес\n3. Хронические заболевания\n"
        "4. Препараты или добавки\n5. Уровень физической активности\n\n"
        "Можно отвечать в свободной форме.",
        parse_mode="HTML", reply_markup=builder.as_markup()
    )
    await state.set_state(OnboardingStates.phase4_followup)

@router.message(OnboardingStates.phase4_followup)
async def phase4(message: Message, state: FSMContext):
    data = await state.get_data()
    await update_consultation_phase(data.get("consultation_id", 0), "phase4_followup", message.text or "")
    await message.answer(
        "<b>Этап 4 из 4:</b> Документы и анализы\n\n"
        "Если есть результаты анализов, выписки — отправьте сейчас (фото или PDF).\n\n"
        "Можно отправить несколько файлов по одному.",
        parse_mode="HTML", reply_markup=after_docs_kb()
    )
    await state.set_state(OnboardingStates.phase5_docs)

@router.message(OnboardingStates.phase5_docs, F.document)
async def receive_document(message: Message, state: FSMContext):
    data = await state.get_data()
    docs = data.get("docs", [])
    docs.append({"type": "document", "file_id": message.document.file_id, "name": message.document.file_name or "документ"})
    await state.update_data(docs=docs)
    await save_document(message.from_user.id, message.document.file_id, "document", message.document.file_name or "")
    await message.answer("✅ Документ получен.\nМожете отправить ещё или нажмите «Всё загружено».", reply_markup=after_docs_kb())

@router.message(OnboardingStates.phase5_docs, F.photo)
async def receive_photo_doc(message: Message, state: FSMContext):
    data = await state.get_data()
    docs = data.get("docs", [])
    photo = message.photo[-1]
    docs.append({"type": "photo", "file_id": photo.file_id})
    await state.update_data(docs=docs)
    await save_document(message.from_user.id, photo.file_id, "photo")
    await message.answer("✅ Фото получено.\nМожете отправить ещё или нажмите «Всё загружено».", reply_markup=after_docs_kb())

@router.callback_query(F.data == "docs_done")
async def docs_done(callback: CallbackQuery, state: FSMContext):
    payment_id = await create_payment(telegram_id=callback.from_user.id, amount=CONSULTATION_PRICE,
        product_type="consultation", product_name="Онлайн-консультация")
    await state.update_data(payment_id=payment_id)
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Я оплатил — отправить чек", callback_data="send_consult_receipt")
    builder.button(text="🏠 В главное меню", callback_data="back_to_menu")
    builder.adjust(1)
    await callback.message.edit_text(
        "✅ Данные собраны.\n\nДля получения персонального заключения — оплатите консультацию:\n\n"
        f"💳 Перевод через Kaspi:\n📱 Номер: <code>{KASPI_PHONE}</code>\n"
        f"👤 Получатель: {KASPI_NAME}\n💰 Сумма: <b>{CONSULTATION_PRICE:,} ₸</b>\n\n"
        "После оплаты нажмите кнопку ниже и пришлите скриншот чека.",
        parse_mode="HTML", reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "send_consult_receipt")
async def send_consult_receipt_prompt(callback: CallbackQuery, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 В главное меню", callback_data="back_to_menu")
    await callback.message.edit_text("📸 Пришлите скриншот или фото чека оплаты.", reply_markup=builder.as_markup())
    await state.set_state(PaymentStates.waiting_receipt)
    await callback.answer()

@router.message(PaymentStates.waiting_receipt, F.photo)
async def receive_consult_receipt(message: Message, state: FSMContext):
    data = await state.get_data()
    payment_id = data.get("payment_id", 0)
    photo = message.photo[-1]
    await attach_receipt(payment_id, photo.file_id)
    if ADMIN_ID:
        user = message.from_user
        name = user.full_name or user.username or str(user.id)
        username = f"@{user.username}" if user.username else "нет username"
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Подтвердить", callback_data=f"adm_approve_{payment_id}")
        builder.button(text="❌ Отклонить", callback_data=f"adm_reject_{payment_id}")
        builder.adjust(2)
        await message.bot.send_photo(chat_id=ADMIN_ID, photo=photo.file_id,
            caption=(f"💳 <b>Оплата консультации</b>\n\nПациент: {name} ({username})\n"
                     f"ID: <code>{user.id}</code>\nСумма: {CONSULTATION_PRICE:,} ₸"),
            parse_mode="HTML", reply_markup=builder.as_markup())
    recs = (
        "Чек получен. Доктор проверит оплату и свяжется с вами.\n\n"
        "А пока — базовый протокол здоровья Medicine 3.0:\n\n"
        "😴 <b>Сон</b>\n7–9 часов. До 23:00. Без синего света за час до сна. 18–20°C в спальне.\n\n"
        "🥗 <b>Питание</b>\nБелок + овощи + здоровые жиры. Без сахара. Последний приём за 3 часа до сна.\n\n"
        "💧 <b>Вода</b>\n30–35 мл на кг веса. Стакан сразу после пробуждения.\n\n"
        "🏃 <b>Физическая активность</b>\n150 мин/неделю. Силовые 2–3 раза. 10 000 шагов в день."
    )
    builder2 = InlineKeyboardBuilder()
    builder2.button(text="📱 Канал доктора", url=CHANNEL_LINK)
    builder2.button(text="🏠 В главное меню", callback_data="back_to_menu")
    builder2.adjust(1)
    await message.answer(recs, parse_mode="HTML", reply_markup=builder2.as_markup())
    await state.clear()
