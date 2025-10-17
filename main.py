import os
import logging
import asyncio
import sys
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
from bot import dp, bot
from admin_panel import dp as admin_dp
from database_adapter import init_db

# Windows'da Unicode belgilar uchun encoding sozlash
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())

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

@app.on_event("startup")
async def startup_event():
    """FastAPI startup event"""
    logger.info("FastAPI application started")
    print("FastAPI application started")

@app.get("/health")
async def health_check():
    """Healthcheck endpoint Railway uchun"""
    try:
        # Simple health check - just return status
        return {"status": "healthy", "service": "telegram-bot", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {"status": "unhealthy", "error": str(e)}

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
        
        logger.info("Starting services...")
        
        # FastAPI server'ni ishga tushirish
        port = int(os.getenv("PORT", 8000))
        logger.info(f"Starting FastAPI server on port {port}")
        
        # FastAPI server'ni alohida task'da ishga tushirish
        async def run_fastapi():
            try:
                config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
                server = uvicorn.Server(config)
                await server.serve()
            except Exception as e:
                logger.error(f"FastAPI server xatoligi: {e}")
                print(f"FastAPI server xatoligi: {e}")
        
        # Bot polling'ni background task sifatida ishga tushirish
        async def run_bot_polling():
            try:
                # FastAPI server ishga tushish uchun kutish
                await asyncio.sleep(5)
                logger.info("Bot polling boshlanmoqda...")
                # Admin panel dispatcher'ini asosiy dispatcher'ga qo'shish
                dp.include_router(admin_dp)
                await dp.start_polling(bot)
            except Exception as e:
                logger.error(f"Bot polling xatoligi: {e}")
                print(f"Bot polling xatoligi: {e}")
        
        # Ikkala service'ni parallel ishga tushirish
        fastapi_task = asyncio.create_task(run_fastapi())
        bot_task = asyncio.create_task(run_bot_polling())
        
        logger.info("All services started successfully")
        print("Bot va FastAPI server ishga tushdi!")
        
        # Ikkala task'ni kutish
        await asyncio.gather(fastapi_task, bot_task)
        
    except Exception as e:
        logger.error(f"Bot ishga tushishda xatolik: {e}")
        print(f"Xatolik: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())