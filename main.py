import os
import logging
import asyncio
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

# Environment o'zgaruvchilar
BOT_TOKEN = os.getenv("BOT_TOKEN")

async def main():
    """Asosiy funksiya - polling rejimida bot ishga tushirish"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN topilmadi!")
        print("❌ BOT_TOKEN environment variable kerak!")
        print("Telegram @BotFather dan bot yaratib, tokenni oling")
        return
    
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY topilmadi!")
        print("❌ OPENAI_API_KEY environment variable kerak!")
        print("OpenAI platformasidan API key oling")
        return
    
    try:
        # Ma'lumotlar bazasini ishga tushirish
        await init_db()
        logger.info("Database initialized successfully")
        
        # Webhookni o'chirish (agar avval o'rnatilgan bo'lsa)
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook deleted, starting polling...")
        
        print("🚀 Bot polling rejimida ishga tushmoqda...")
        
        # Polling ishga tushirish
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Bot ishga tushishda xatolik: {e}")
        print(f"❌ Xatolik: {e}")

if __name__ == "__main__":
    asyncio.run(main())