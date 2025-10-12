import asyncio
import logging
import os
from dotenv import load_dotenv
from bot import dp, bot
from database import init_db

# .env faylini yuklash
load_dotenv()

# Logging sozlash
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Botni polling rejimida ishga tushirish"""
    
    # Ma'lumotlar bazasini ishga tushirish
    await init_db()
    logger.info("Database initialized successfully")
    
    # Webhook ni o'chirish (agar o'rnatilgan bo'lsa)
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Webhook deleted, starting polling...")
    
    # Botni ishga tushirish
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Bot polling error: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    # Environment o'zgaruvchilarini tekshirish
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        print("BOT_TOKEN environment variable kerak!")
        print("Telegram @BotFather dan bot yaratib, tokenni oling")
        exit(1)
    
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY environment variable kerak!")
        print("OpenAI platformasidan API key oling")
        exit(1)
    
    print("Bot polling rejimida ishga tushmoqda...")
    
    # Botni ishga tushirish
    asyncio.run(main())
