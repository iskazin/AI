from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Пройти диагностику", callback_data="start_consultation")
    builder.button(text="📚 Авторские гайды", callback_data="guides_list")
    builder.button(text="💬 Записаться на консультацию", url="https://t.me/AibatyrIskazin_bot")
    builder.button(text="📱 Канал доктора", url="https://t.me/dr_iskazin")
    builder.adjust(1)
    return builder.as_markup()


def guides_list_keyboard(guides: list):
    builder = InlineKeyboardBuilder()
    for g in guides:
        builder.button(
            text=f"{g['title']} — {g['price_kzt']:,} ₸",
            callback_data=f"guide_{g['id']}"
        )
    builder.button(text="🏠 В главное меню", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()


def guide_detail_keyboard(guide_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Купить через Kaspi", callback_data=f"buy_guide_{guide_id}")
    builder.button(text="← Назад к гайдам", callback_data="guides_list")
    builder.button(text="🏠 В главное меню", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()


def payment_keyboard(kaspi_phone: str):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Я оплатил — отправить чек", callback_data="send_receipt")
    builder.button(text="🏠 В главное меню", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()


def back_to_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 В главное меню", callback_data="back_to_menu")
    return builder.as_markup()
