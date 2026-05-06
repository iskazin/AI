"""
main.py — точка входа Neo Clinic Bot
"""
import asyncio
import logging
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from database.db import init_db
from handlers import common, admin, onboarding, guides

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN не установлен в переменных окружения")

    await init_db()
    logger.info("База данных инициализирована")

    bot = Bot(token=token)
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрация роутеров — порядок важен
    dp.include_router(common.router)
    dp.include_router(admin.router)
    dp.include_router(guides.router)
    dp.include_router(onboarding.router)

    logger.info("Neo Clinic Bot запускается...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
