"""
handlers/admin.py
Админ-панель — пациенты, карточки, платежи, документы
"""
import os
import aiosqlite
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import (
    get_all_patients, get_patient_card, get_pending_payments,
    approve_payment, reject_payment, get_stats, get_patient_documents
)

router = Router()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB_PATH = os.getenv("DB_PATH", "neo_clinic.db")


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


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


@router.callback_query(F.data == "adm_stats")
async def adm_stats(callback: CallbackQuery):
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
        builder.button(text=f"📋 {name[:20]}", callback_data=f"adm_card_{p['telegram_id']}")
    builder.adjust(1)
    if offset > 0:
        builder.button(text="← Назад", callback_data=f"adm_patients_{offset - 8}")
    if len(patients) == 8:
        builder.button(text="Далее →", callback_data=f"adm_patients_{offset + 8}")
    builder.button(text="🏠 Меню", callback_data="adm_back")
    builder.adjust(1)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


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
    consultations = data.get("consultations", [])
    payments = data.get("payments", [])
    total = sum(pay["amount"] for pay in payments if pay["status"] == "approved")
    docs = await get_patient_documents(telegram_id)
    docs_count = len(docs)
    text = (
        f"👤 <b>{name}</b>\n"
        f"Telegram: {username}\n"
        f"ID: <code>{telegram_id}</code>\n"
        f"Дата регистрации: {registered}\n\n"
        f"📋 Консультаций: <b>{len(consultations)}</b>\n"
        f"💰 Оплачено: <b>{total:,} ₸</b>\n"
        f"📎 Документов: <b>{docs_count}</b>"
    )
    builder = InlineKeyboardBuilder()
    if consultations:
        builder.button(text="📖 Читать ответы", callback_data=f"adm_consult_{telegram_id}_0")
    if docs_count > 0:
        builder.button(text=f"📎 Документы ({docs_count})", callback_data=f"adm_docs_{telegram_id}")
    if payments:
        builder.button(text="💳 История платежей", callback_data=f"adm_payments_{telegram_id}")
    builder.button(text="← К списку", callback_data="adm_patients_0")
    builder.button(text="🏠 Меню", callback_data="adm_back")
    builder.adjust(1)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("adm_docs_"))
async def adm_docs(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Доступ закрыт.")
    telegram_id = int(callback.data.split("_")[-1])
    docs = await get_patient_documents(telegram_id)
    if not docs:
        await callback.answer("Документов нет.", show_alert=True)
        return
    await callback.answer()
    await callback.bot.send_message(
        chat_id=callback.from_user.id,
        text=f"📎 <b>Документы пациента ({len(docs)} шт.)</b>",
        parse_mode="HTML"
    )
    for doc in docs:
        try:
            date = doc.get("created_at", "")[:10]
            if doc["file_type"] == "photo":
                await callback.bot.send_photo(
                    chat_id=callback.from_user.id,
                    photo=doc["file_id"],
                    caption=f"🖼 Фото · {date}"
                )
            else:
                await callback.bot.send_document(
                    chat_id=callback.from_user.id,
                    document=doc["file_id"],
                    caption=f"📄 {doc.get('file_name', 'документ')} · {date}"
                )
        except Exception:
            pass
    builder = InlineKeyboardBuilder()
    builder.button(text="← К карточке", callback_data=f"adm_card_{telegram_id}")
    await callback.bot.send_message(
        chat_id=callback.from_user.id,
        text="Все документы отправлены.",
        reply_markup=builder.as_markup()
    )


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

    def fmt(label, val):
        val = (val or "").strip()
        return f"\n<b>{label}:</b>\n{val}\n" if val else ""

    text = (
        f"📋 <b>Консультация #{idx + 1}</b> от {date}\n"
        f"Статус: {status}\n"
        f"{fmt('Жалобы', c.get('phase2_complaints'))}"
        f"{fmt('История болезни', c.get('phase3_history'))}"
        f"{fmt('Доп. данные', c.get('phase4_followup'))}"
    )
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
        emoji = {"approved": "✅", "pending": "⏳", "rejected": "❌"}.get(pay["status"], "❓")
        text += (
            f"{emoji} <b>{pay['amount']:,} ₸</b> — {pay.get('product_name') or pay['product_type']}\n"
            f"   {pay['created_at'][:10]}\n\n"
        )
    builder = InlineKeyboardBuilder()
    builder.button(text="← К карточке", callback_data=f"adm_card_{telegram_id}")
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "adm_pending")
async def adm_pending(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("Доступ закрыт.")
    payments = await get_pending_payments()
    if not payments:
        builder = InlineKeyboardBuilder()
        builder.button(text="← Назад", callback_data="adm_back")
        await callback.message.edit_text("✅ Нет ожидающих платежей.", reply_markup=builder.as_markup())
        await callback.answer()
        return
    text = f"⏳ <b>Ожидают подтверждения: {len(payments)}</b>\n\n"
    builder = InlineKeyboardBuilder()
    for pay in payments:
        name = pay.get("full_name") or pay.get("username") or f"ID {pay['telegram_id']}"
        product = pay.get("product_name") or pay.get("product_type", "")
        text += f"• <b>{name}</b> — {pay['amount']:,} ₸ ({product})\n"
        builder.button(text=f"✅ {name[:15]} {pay['amount']:,}₸", callback_data=f"adm_approve_{pay['id']}")
        builder.button(text="❌", callback_data=f"adm_reject_{pay['id']}")
    builder.button(text="← Назад", callback_data="adm_back")
    builder.adjust(2)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("adm_approve_"))
async def adm_approve(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer()
    payment_id = int(callback.data.split("_")[-1])
    await approve_payment(payment_id)
    await callback.answer("✅ Платёж подтверждён", show_alert=True)
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
            payment = await cursor.fetchone()
            payment = dict(payment) if payment else {}
    except Exception:
        payment = {}
    if payment:
        telegram_id = payment.get("telegram_id")
        card = await get_patient_card(telegram_id)
        consultations = card.get("consultations", [])
        patient = card.get("patient", {})
        name = patient.get("full_name") or patient.get("username") or str(telegram_id)
        if consultations:
            c = consultations[0]
            summary = (
                f"📋 <b>Карточка: {name}</b>\n\n"
                f"<b>Жалобы:</b>\n{c.get('phase2_complaints') or '—'}\n\n"
                f"<b>История:</b>\n{c.get('phase3_history') or '—'}\n\n"
                f"<b>Доп. данные:</b>\n{c.get('phase4_followup') or '—'}"
            )
            if len(summary) > 4000:
                summary = summary[:3900] + "\n\n<i>... обрезано</i>"
            await callback.bot.send_message(
                chat_id=callback.from_user.id, text=summary, parse_mode="HTML"
            )
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
                            chat_id=callback.from_user.id, photo=doc["file_id"],
                            caption=f"🖼 {doc.get('created_at', '')[:10]}"
                        )
                    else:
                        await callback.bot.send_document(
                            chat_id=callback.from_user.id, document=doc["file_id"],
                            caption=f"📄 {doc.get('file_name', 'документ')}"
                        )
                except Exception:
                    pass
        try:
            builder = InlineKeyboardBuilder()
            builder.button(text="📱 Канал доктора", url="https://t.me/dr_iskazin")
            builder.button(text="🏠 В главное меню", callback_data="back_to_menu")
            builder.adjust(1)
            await callback.bot.send_message(
                chat_id=telegram_id,
                text="✅ Оплата подтверждена.\n\nДоктор Айбатыр Исказин свяжется с вами в ближайшее время.",
                reply_markup=builder.as_markup()
            )
        except Exception:
            pass
    payments = await get_pending_payments()
    if not payments:
        builder = InlineKeyboardBuilder()
        builder.button(text="← Меню", callback_data="adm_back")
        try:
            await callback.message.edit_text("✅ Все платежи подтверждены.", reply_markup=builder.as_markup())
        except Exception:
            pass
    else:
        await adm_pending(callback)


@router.callback_query(F.data.startswith("adm_reject_"))
async def adm_reject(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer()
    payment_id = int(callback.data.split("_")[-1])
    await reject_payment(payment_id)
    await callback.answer("❌ Платёж отклонён", show_alert=True)
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT telegram_id FROM payments WHERE id = ?", (payment_id,))
            row = await cursor.fetchone()
            if row:
                await callback.bot.send_message(
                    chat_id=row["telegram_id"],
                    text="❌ Оплата не подтверждена.\n\nПроверьте скриншот чека и попробуйте снова."
                )
    except Exception:
        pass
    await adm_pending(callback)


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
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_main_keyboard())
    await callback.answer()
