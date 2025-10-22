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
    print("FastAPI application started")
    # Bot'ni background'da ishga tushirish
    asyncio.create_task(start_bot())

@app.get("/health")
async def health_check():
    """Healthcheck endpoint Railway uchun"""
    return JSONResponse(
        status_code=200,
        content={"status": "healthy", "timestamp": datetime.now().isoformat()}
    )

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Telegram Bot is running", "status": "active"}

async def start_bot():
    """Bot'ni ishga tushirish funksiyasi"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN topilmadi!")
        print("BOT_TOKEN environment variable kerak!")
        return
    
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY topilmadi!")
        print("OPENAI_API_KEY environment variable kerak!")
        return
    
    try:
        # Ma'lumotlar bazasini ishga tushirish
        await init_db()
        print("Database initialized successfully")
        
        # Webhookni to'liq o'chirish
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            print("Webhook deleted successfully")
        except Exception as e:
            print(f"Webhook o'chirishda xatolik: {e}")
        
        print("Starting bot polling...")
        # Bot polling'ni ishga tushirish
        await dp.start_polling(bot)
        
    except Exception as e:
        print(f"Bot ishga tushishda xatolik: {e}")
        logger.error(f"Bot error: {e}")

def start_services():
    """Asosiy funksiya - FastAPI server'ni ishga tushirish"""
    port = int(os.getenv("PORT", 8000))
    print(f"Starting FastAPI server on port {port}")
    
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

if __name__ == "__main__":
    start_services()