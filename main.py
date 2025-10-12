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
        
        # Webhookni to'liq o'chirish (agar avval o'rnatilgan bo'lsa)
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("Webhook deleted successfully")
            
            # Webhook holatini tekshirish
            webhook_info = await bot.get_webhook_info()
            if webhook_info.url:
                logger.warning(f"Webhook hali ham faol: {webhook_info.url}")
                # Qo'shimcha urinish
                await bot.delete_webhook(drop_pending_updates=True)
                logger.info("Webhook qaytadan o'chirildi")
            else:
                logger.info("Webhook to'liq o'chirildi")
                
        except Exception as e:
            logger.error(f"Webhook o'chirishda xatolik: {e}")
        
        logger.info("Starting polling...")
        
        # Railway da bot restart qilish uchun kichik kutish
        await asyncio.sleep(2)
        
        print("🚀 Bot polling rejimida ishga tushmoqda...")
        
        # Polling ishga tushirish
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Bot ishga tushishda xatolik: {e}")
        print(f"❌ Xatolik: {e}")

if __name__ == "__main__":
    asyncio.run(main())