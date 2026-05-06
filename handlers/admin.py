"""
handlers/admin.py
Админ-панель для доктора — пациенты, карточки, платежи, статистика
"""
import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import (
    get_all_patients, get_patient_card, get_pending_payments,
    approve_payment, reject_payment, get_stats
)

router = Router()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


# ─── Главное меню админки ──────────────────────────────────────────────────

def admin_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Пациенты", callback_data="adm_patients_0")
    builder.button(text="⏳ Ожидают оплаты", callback_data="adm_pending")
    builder.button(text="📊 Статистика", callback_data="adm_stats")
    builder.adjust(2, 1)
    return builder.as_markup()


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("Доступ закрыт.")
        return

    stats = await get_stats()
    text = (
        "🏥 <b>Neo Clinic — Панель администратора</b>\n\n"
        f"👥 Пациентов всего: <b>{stats['total_patients']}</b>\n"
        f"📋 Консультаций: <b>{stats['total_consultations']}</b>\n"
        f"⏳ Ожидают подтверждения: <b>{stats['pending_payments']}</b>\n"
        f"💰 Выручка: <b>{stats['total_revenue']:,} ₸</b>\n"
        f"🆕 Новых за неделю: <b>{stats['new_this_week']}</b>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=admin_main_keyboard())


# ─── Статистика ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_approve_"))
async def adm_approve(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Доступ закрыт.")

    stats = await get_stats()
    text = (
        "📊 <b>Статистика Neo Clinic</b>\n\n"
        f"👥 Пациентов всего: <b>{stats['total_patients']}</b>\n"
        f"🆕 Новых за неделю: <b>{stats['new_this_week']}</b>\n"
        f"📋 Консультаций: <b>{stats['total_consultations']}</b>\n"
        f"⏳ Ожидают оплаты: <b>{stats['pending_payments']}</b>\n"
        f"💰 Общая выручка: <b>{stats['total_revenue']:,} ₸</b>"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="← Назад", callback_data="adm_back")
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


# ─── Список пациентов ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_patients_"))
async def adm_patients(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Доступ закрыт.")

    offset = int(callback.data.split("_")[-1])
    patients = await get_all_patients(limit=8, offset=offset)

    if not patients:
        await callback.answer("Пациентов нет.", show_alert=True)
        return

    text = f"👥 <b>Пациенты</b> (с {offset + 1}):\n\n"
    builder = InlineKeyboardBuilder()

    for p in patients:
        name = p.get("full_name") or p.get("username") or f"ID {p['telegram_id']}"
        consultations = p.get("consultation_count", 0)
        paid = p.get("total_paid", 0) or 0
        text += f"• <b>{name}</b> — {consultations} конс., {paid:,} ₸\n"
        builder.button(
            text=f"📋 {name[:20]}",
            callback_data=f"adm_card_{p['telegram_id']}"
        )

    builder.adjust(1)

    nav_row = []
    if offset > 0:
        builder.button(text="← Назад", callback_data=f"adm_patients_{offset - 8}")
    if len(patients) == 8:
        builder.button(text="Далее →", callback_data=f"adm_patients_{offset + 8}")
    builder.button(text="🏠 Меню", callback_data="adm_back")
    builder.adjust(1)

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


# ─── Карточка пациента ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_card_"))
async def adm_card(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Доступ закрыт.")

    telegram_id = int(callback.data.split("_")[-1])
    data = await get_patient_card(telegram_id)

    if not data:
        await callback.answer("Пациент не найден.", show_alert=True)
        return

    p = data["patient"]
    name = p.get("full_name") or p.get("username") or f"ID {telegram_id}"
    username = f"@{p['username']}" if p.get("username") else "нет username"
    registered = p.get("registered_at", "—")[:10]

    text = (
        f"👤 <b>{name}</b>\n"
        f"Telegram: {username}\n"
        f"ID: <code>{telegram_id}</code>\n"
        f"Дата регистрации: {registered}\n\n"
    )

    # Консультации
    consultations = data.get("consultations", [])
    if consultations:
        text += f"📋 <b>Консультаций: {len(consultations)}</b>\n"
    else:
        text += "📋 Консультаций пока нет\n"

    # Платежи
    payments = data.get("payments", [])
    if payments:
        total = sum(p["amount"] for p in payments if p["status"] == "approved")
        text += f"💰 Оплачено: <b>{total:,} ₸</b>\n"
    else:
        text += "💰 Платежей нет\n"

    builder = InlineKeyboardBuilder()

    if consultations:
        builder.button(
            text="📖 Читать ответы",
            callback_data=f"adm_consult_{telegram_id}_0"
        )
    if payments:
        builder.button(
            text="💳 История платежей",
            callback_data=f"adm_payments_{telegram_id}"
        )

    builder.button(text="← К списку", callback_data="adm_patients_0")
    builder.button(text="🏠 Меню", callback_data="adm_back")
    builder.adjust(1)

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


# ─── Ответы пациента по консультации ──────────────────────────────────────

@router.callback_query(F.data.startswith("adm_consult_"))
async def adm_consult(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Доступ закрыт.")

    parts = callback.data.split("_")
    telegram_id = int(parts[2])
    idx = int(parts[3])

    data = await get_patient_card(telegram_id)
    consultations = data.get("consultations", [])

    if not consultations or idx >= len(consultations):
        await callback.answer("Нет данных.", show_alert=True)
        return

    c = consultations[idx]
    date = c.get("created_at", "—")[:10]
    status = c.get("status", "—")

    def fmt(label: str, val: str) -> str:
        val = val.strip() if val else ""
        if not val:
            return ""
        return f"\n<b>{label}:</b>\n{val}\n"

    text = (
        f"📋 <b>Консультация #{idx + 1}</b> от {date}\n"
        f"Статус: {status}\n"
        f"{fmt('Жалобы', c.get('phase2_complaints', ''))}"
        f"{fmt('История болезни', c.get('phase3_history', ''))}"
        f"{fmt('Доп. вопросы', c.get('phase4_followup', ''))}"
        f"{fmt('Заключение', c.get('phase5_result', ''))}"
    )

    # Обрезаем если слишком длинный
    if len(text) > 4000:
        text = text[:3900] + "\n\n<i>... текст обрезан</i>"

    builder = InlineKeyboardBuilder()

    if idx > 0:
        builder.button(text=f"← Конс. #{idx}", callback_data=f"adm_consult_{telegram_id}_{idx-1}")
    if idx < len(consultations) - 1:
        builder.button(text=f"Конс. #{idx+2} →", callback_data=f"adm_consult_{telegram_id}_{idx+1}")

    builder.button(text="← К карточке", callback_data=f"adm_card_{telegram_id}")
    builder.adjust(2, 1)

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


# ─── История платежей пациента ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_payments_"))
async def adm_payments_patient(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Доступ закрыт.")

    telegram_id = int(callback.data.split("_")[-1])
    data = await get_patient_card(telegram_id)
    payments = data.get("payments", [])

    if not payments:
        await callback.answer("Платежей нет.", show_alert=True)
        return

    text = "💳 <b>История платежей:</b>\n\n"
    for pay in payments:
        status_emoji = {"approved": "✅", "pending": "⏳", "rejected": "❌"}.get(pay["status"], "❓")
        text += (
            f"{status_emoji} <b>{pay['amount']:,} ₸</b> — {pay.get('product_name') or pay['product_type']}\n"
            f"   {pay['created_at'][:10]}\n\n"
        )

    builder = InlineKeyboardBuilder()
    builder.button(text="← К карточке", callback_data=f"adm_card_{telegram_id}")
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


# ─── Ожидающие платежи ─────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_pending")
async def adm_pending(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Доступ закрыт.")

    payments = await get_pending_payments()

    if not payments:
        builder = InlineKeyboardBuilder()
        builder.button(text="← Назад", callback_data="adm_back")
        await callback.message.edit_text(
            "✅ Нет ожидающих платежей.",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
        return

    text = f"⏳ <b>Ожидают подтверждения: {len(payments)}</b>\n\n"
    builder = InlineKeyboardBuilder()

    for pay in payments:
        name = pay.get("full_name") or pay.get("username") or f"ID {pay['telegram_id']}"
        product = pay.get("product_name") or pay.get("product_type", "")
        text += f"• <b>{name}</b> — {pay['amount']:,} ₸ ({product})\n"
        builder.button(
            text=f"✅ {name[:15]} {pay['amount']:,}₸",
            callback_data=f"adm_approve_{pay['id']}"
        )
        builder.button(
            text="❌",
            callback_data=f"adm_reject_{pay['id']}"
        )

    builder.button(text="← Назад", callback_data="adm_back")
    builder.adjust(2)

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("adm_approve_"))
async def adm_approve(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer()

    payment_id = int(callback.data.split("_")[-1])
    await approve_payment(payment_id)
    await callback.answer("✅ Платёж подтверждён", show_alert=True)

    # Получить данные платежа и пациента
    from database.db import get_patient_card
    async with __import__('aiosqlite').connect(os.getenv("DB_PATH", "neo_clinic.db")) as db:
        db.row_factory = __import__('aiosqlite').Row
        cursor = await db.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
        payment = await cursor.fetchone()

    if payment:
        telegram_id = payment["telegram_id"]
        data = await get_patient_card(telegram_id)
        patient = data.get("patient", {})
        consultations = data.get("consultations", [])
        name = patient.get("full_name") or patient.get("username") or str(telegram_id)

        # Отправить сводку пациента
        if consultations:
            c = consultations[0]
            summary = (
                f"📋 <b>Карточка пациента: {name}</b>\n\n"
                f"<b>Жалобы:</b>\n{c.get('phase2_complaints') or '—'}\n\n"
                f"<b>История:</b>\n{c.get('phase3_history') or '—'}\n\n"
                f"<b>Доп. данные:</b>\n{c.get('phase4_followup') or '—'}"
            )
            if len(summary) > 4000:
                summary = summary[:3900] + "\n\n<i>... текст обрезан</i>"

            await callback.bot.send_message(
                chat_id=callback.from_user.id,
                text=summary,
                # Переслать все документы пациента
        from database.db import get_patient_documents
        docs = await get_patient_documents(telegram_id)
        if docs:
            await callback.bot.send_message(
                chat_id=callback.from_user.id,
                text=f"📎 Документы пациента ({len(docs)} шт.):"
            )
            for doc in docs:
                try:
                    if doc["file_type"] == "photo":
                        await callback.bot.send_photo(
                            chat_id=callback.from_user.id,
                            photo=doc["file_id"]
                        )
                    else:
                        await callback.bot.send_document(
                            chat_id=callback.from_user.id,
                            document=doc["file_id"],
                            caption=doc.get("file_name", "документ")
                        )
                except Exception:
                    pass
                parse_mode="HTML"
            )

        # Уведомить пациента
        try:
            builder = InlineKeyboardBuilder()
            builder.button(text="📱 Канал доктора", url="https://t.me/dr_iskazin")
            builder.button(text="🏠 В главное меню", callback_data="back_to_menu")
            builder.adjust(1)
            await callback.bot.send_message(
                chat_id=telegram_id,
                text=(
                    "✅ Оплата подтверждена.\n\n"
                    "Доктор Айбатыр Исказин свяжется с вами в ближайшее время "
                    "для передачи персонального заключения."
                ),
                reply_markup=builder.as_markup()
            )
        except Exception:
            pass

    # Обновить список ожидающих
    payments = await get_pending_payments()
    if not payments:
        builder = InlineKeyboardBuilder()
        builder.button(text="← Назад", callback_data="adm_back")
        await callback.message.edit_text("✅ Все платежи подтверждены.", reply_markup=builder.as_markup())
    else:
        await adm_pending(callback)


# ─── Возврат в меню ────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_back")
async def adm_back(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer()

    stats = await get_stats()
    text = (
        "🏥 <b>Neo Clinic — Панель администратора</b>\n\n"
        f"👥 Пациентов всего: <b>{stats['total_patients']}</b>\n"
        f"📋 Консультаций: <b>{stats['total_consultations']}</b>\n"
        f"⏳ Ожидают подтверждения: <b>{stats['pending_payments']}</b>\n"
        f"💰 Выручка: <b>{stats['total_revenue']:,} ₸</b>\n"
        f"🆕 Новых за неделю: <b>{stats['new_this_week']}</b>"
    )
    await callback.message.edit_text(
        text, parse_mode="HTML", reply_markup=admin_main_keyboard()
    )
    await callback.answer()
