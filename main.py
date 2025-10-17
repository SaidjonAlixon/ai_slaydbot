import os
import logging
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
from bot import dp, bot
from database_adapter import init_db

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
        
        # Bot polling'ni background task sifatida ishga tushirish
        async def run_bot_polling():
            await dp.start_polling(bot)
        
        # Bot polling'ni background task sifatida ishga tushirish
        bot_task = asyncio.create_task(run_bot_polling())
        
        # FastAPI server'ni ishga tushirish
        port = int(os.getenv("PORT", 8000))
        config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
        server = uvicorn.Server(config)
        
        # FastAPI server va bot polling'ni parallel ishga tushirish
        await asyncio.gather(server.serve(), bot_task)
        
    except Exception as e:
        logger.error(f"Bot ishga tushishda xatolik: {e}")
        print(f"Xatolik: {e}")

if __name__ == "__main__":
    asyncio.run(main())