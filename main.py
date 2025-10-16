import os
import logging
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
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

# FastAPI app yaratish
app = FastAPI(title="Telegram Bot API", version="1.0.0")

@app.get("/health")
async def health_check():
    """Healthcheck endpoint Railway uchun"""
    return JSONResponse(
        status_code=200,
        content={"status": "healthy", "service": "telegram-bot"}
    )

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Telegram Bot is running", "status": "active"}

async def main():
    """Asosiy funksiya - polling rejimida bot ishga tushirish"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN topilmadi!")
        print("BOT_TOKEN environment variable kerak!")
        print("Telegram @BotFather dan bot yaratib, tokenni oling")
        return
    
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY topilmadi!")
        print("OPENAI_API_KEY environment variable kerak!")
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
        
        print("Bot polling rejimida ishga tushmoqda...")
        
        # FastAPI server va bot polling'ni parallel ishga tushirish
        import threading
        
        # Bot polling'ni alohida thread'da ishga tushirish
        def run_bot():
            asyncio.run(dp.start_polling(bot))
        
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()
        
        # FastAPI server'ni ishga tushirish
        port = int(os.getenv("PORT", 8000))
        uvicorn.run(app, host="0.0.0.0", port=port)
        
    except Exception as e:
        logger.error(f"Bot ishga tushishda xatolik: {e}")
        print(f"Xatolik: {e}")

if __name__ == "__main__":
    asyncio.run(main())