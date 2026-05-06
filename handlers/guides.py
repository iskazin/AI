"""
handlers/guides.py
Авторские гайды — каталог, детали, оплата через Kaspi
"""
import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, PhotoSize
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from states.states import PaymentStates
from database.db import create_payment, attach_receipt
from keyboards.keyboards import back_to_menu_keyboard

router = Router()

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
KASPI_PHONE = os.getenv("KASPI_PHONE", "+77771080196")
KASPI_NAME = os.getenv("KASPI_NAME", "Айбатыр Исказин")

GUIDES = [
    {"id": 1, "title": "Матрица Биомаркеров 100+",
     "description": "Таблица оптимальных (не референсных) значений анализов для Longevity. Список лабораторий и периодичность сдачи.",
     "price_kzt": 12000},
    {"id": 2, "title": "Anti-Glycation: Стратегия Чистых Сосудов",
     "description": "Руководство по защите сосудов и кожи от сахара. Список продуктов-ингибиторов гликации и правила термической обработки.",
     "price_kzt": 9000},
    {"id": 3, "title": "Горметический Скрипт: Искусство Правильного Стресса",
     "description": "Практическое руководство по внедрению холодовых пауз, сауны и гипоксии для активации генов долголетия.",
     "price_kzt": 7500},
    {"id": 4, "title": "Архитектура Сна: Протокол Восстановления Ресурса",
     "description": "Чек-лист по настройке спальни, блокировке синего света и добавкам для глубокой фазы сна.",
     "price_kzt": 8500},
    {"id": 5, "title": "Нутри-Стек: Базовый Протокол Долголетия",
     "description": "Список из 5 базовых добавок с доказанной эффективностью (Medicine 3.0), их дозировки и формы.",
     "price_kzt": 10000},
    {"id": 6, "title": "Метаболический Переключатель: 48 часов Ребута",
     "description": "Пошаговый план питания и активности на 2 дня для повышения чувствительности к инсулину.",
     "price_kzt": 11500},
    {"id": 7, "title": "Атлас Когнитивного Резерва",
     "description": "Набор нейропротоколов и нутрицевтиков для защиты мозга и улучшения фокуса.",
     "price_kzt": 13000},
    {"id": 8, "title": "Паспорт Тела: Гид по DEXA-сканированию",
     "description": "Инструкция: как читать результаты DEXA, на какие цифры смотреть (висцеральный жир, ALM индекс) и что с этим делать.",
     "price_kzt": 9500},
    {"id": 9, "title": "Longevity Travel Kit: Биохакинг в Путешествиях",
     "description": "Список средств и привычек для минимизации вреда от перелетов, смены часовых поясов и радиации.",
     "price_kzt": 7000},
    {"id": 10, "title": "Вектор Долголетия: Интеллектуальный Экспресс-Аудит",
     "description": "Доступ к автоматизированному опроснику, который выдает отчет по текущим зонам риска старения.",
     "price_kzt": 15000},
]


def get_guide(guide_id: int) -> dict | None:
    for g in GUIDES:
        if g["id"] == guide_id:
            return g
    return None


# ─── Список гайдов ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "guides_list")
async def guides_list(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    for g in GUIDES:
        builder.button(
            text=f"{g['title'][:35]} — {g['price_kzt']:,} ₸",
            callback_data=f"guide_{g['id']}"
        )
    builder.button(text="🏠 В главное меню", callback_data="back_to_menu")
    builder.adjust(1)

    await callback.message.edit_text(
        "📚 <b>Авторские гайды Айбатыра Исказина</b>\n\n"
        "Выберите гайд для подробной информации:",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


# ─── Детали гайда ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("guide_") & ~F.data.startswith("guide_list"))
async def guide_detail(callback: CallbackQuery):
    guide_id = int(callback.data.split("_")[1])
    guide = get_guide(guide_id)

    if not guide:
        await callback.answer("Гайд не найден.", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.button(text=f"💳 Купить — {guide['price_kzt']:,} ₸", callback_data=f"buy_guide_{guide_id}")
    builder.button(text="← Все гайды", callback_data="guides_list")
    builder.button(text="🏠 В главное меню", callback_data="back_to_menu")
    builder.adjust(1)

    await callback.message.edit_text(
        f"📖 <b>{guide['title']}</b>\n\n"
        f"{guide['description']}\n\n"
        f"Стоимость: <b>{guide['price_kzt']:,} ₸</b>",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


# ─── Оплата гайда ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("buy_guide_"))
async def buy_guide(callback: CallbackQuery, state: FSMContext):
    guide_id = int(callback.data.split("_")[2])
    guide = get_guide(guide_id)

    if not guide:
        await callback.answer("Гайд не найден.", show_alert=True)
        return

    payment_id = await create_payment(
        telegram_id=callback.from_user.id,
        amount=guide["price_kzt"],
        product_type="guide",
        product_name=guide["title"],
        product_id=guide["id"]
    )
    await state.update_data(payment_id=payment_id, guide_id=guide_id)

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отправить скриншот оплаты", callback_data="send_guide_receipt")
    builder.button(text="🏠 В главное меню", callback_data="back_to_menu")
    builder.adjust(1)

    await callback.message.edit_text(
        f"💳 <b>Оплата гайда:</b>\n{guide['title']}\n\n"
        f"Сумма: <b>{guide['price_kzt']:,} ₸</b>\n\n"
        f"Переведите через Kaspi:\n"
        f"📱 Номер: <code>{KASPI_PHONE}</code>\n"
        f"👤 Получатель: {KASPI_NAME}\n\n"
        "После оплаты нажмите кнопку ниже и пришлите скриншот.",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "send_guide_receipt")
async def send_guide_receipt_prompt(callback: CallbackQuery, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 В главное меню", callback_data="back_to_menu")

    await callback.message.edit_text(
        "📸 Пришлите скриншот или фото чека оплаты.\n\n"
        "Доктор подтвердит и вы получите доступ к гайду.",
        reply_markup=builder.as_markup()
    )
    await state.set_state(PaymentStates.waiting_guide_receipt)
    await callback.answer()


@router.message(PaymentStates.waiting_guide_receipt, F.photo)
async def receive_guide_receipt(message: Message, state: FSMContext):
    data = await state.get_data()
    payment_id = data.get("payment_id", 0)
    guide_id = data.get("guide_id", 0)
    guide = get_guide(guide_id)

    photo: PhotoSize = message.photo[-1]
    await attach_receipt(payment_id, photo.file_id)

    # Уведомить доктора
    if ADMIN_ID:
        user = message.from_user
        name = user.full_name or user.username or str(user.id)
        username = f"@{user.username}" if user.username else "нет username"
        guide_name = guide["title"] if guide else f"Гайд #{guide_id}"

        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Подтвердить", callback_data=f"adm_approve_{payment_id}")
        builder.button(text="❌ Отклонить", callback_data=f"adm_reject_{payment_id}")
        builder.adjust(2)

        await message.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo.file_id,
            caption=(
                f"💳 <b>Новая оплата гайда</b>\n\n"
                f"Пациент: {name} ({username})\n"
                f"Гайд: {guide_name}\n"
                f"Сумма: {guide['price_kzt']:,} ₸"
            ),
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )

    await message.answer(
        "Чек получен. Доктор проверит оплату в течение нескольких часов.\n\n"
        "После подтверждения вы получите гайд.",
        reply_markup=back_to_menu_keyboard()
    )
    await state.clear()
