from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
import os
import logging
import asyncio
from dotenv import load_dotenv
from bot import dp, bot
from database import init_db

# .env faylini yuklash
load_dotenv()

# FastAPI ilovasi yaratish
app = FastAPI(title="Telegram Presentation Bot")

# Logging sozlash
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment o'zgaruvchilar
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_HOST = os.getenv("RAILWAY_PUBLIC_DOMAIN", os.getenv("RAILWAY_STATIC_URL", "0.0.0.0"))
WEBHOOK_PORT = int(os.getenv("PORT", "8000"))
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}" if BOT_TOKEN else "/webhook"

# Public URL for webhook (Railway domain required for Telegram to reach it)
if WEBHOOK_HOST != "0.0.0.0":
    WEBHOOK_URL = f"https://{WEBHOOK_HOST}{WEBHOOK_PATH}"
else:
    WEBHOOK_URL = f"http://{WEBHOOK_HOST}:{WEBHOOK_PORT}{WEBHOOK_PATH}"

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "OK", "message": "Bot is running"}

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Telegram Presentation Bot API", "status": "active"}

async def setup_webhook():
    """Webhook o'rnatish"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN topilmadi!")
        return
    
    try:
        # Ma'lumotlar bazasini ishga tushirish
        await init_db()
        logger.info("Database initialized successfully")
        
        # Avval webhookni o'chirish
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Old webhook deleted")
        
        # Yangi webhook o'rnatish
        await bot.set_webhook(
            url=WEBHOOK_URL,
            drop_pending_updates=True
        )
        logger.info(f"Webhook set to {WEBHOOK_URL}")
        
        # Webhook holatini tekshirish
        webhook_info = await bot.get_webhook_info()
        logger.info(f"Webhook info: {webhook_info}")
        
    except Exception as e:
        logger.error(f"Webhook setup error: {e}")

async def on_startup():
    """Ilova ishga tushishida"""
    await setup_webhook()

async def on_shutdown():
    """Ilova to'xtashida"""
    if BOT_TOKEN:
        await bot.delete_webhook()
        logger.info("Webhook deleted")

# FastAPI bilan aiogram ni bog'lash
@app.post(WEBHOOK_PATH)
async def webhook_handler(request: Request):
    """Telegram webhook handler"""
    try:
        data = await request.json()
        await dp.feed_webhook_update(bot, data)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    # Uvicorn ishga tushirish
    import uvicorn
    
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN environment variable kerak!")
        print("Telegram @BotFather dan bot yaratib, tokenni oling")
        exit(1)
    
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY environment variable kerak!")
        print("OpenAI platformasidan API key oling")
        exit(1)
    
    print(f"🚀 Bot ishga tushmoqda: http://{WEBHOOK_HOST}:{WEBHOOK_PORT}")
    print(f"📡 Webhook: {WEBHOOK_URL}")
    
    # FastAPI event handlers
    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
    
    # Server ishga tushirish (Railway uchun)
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=WEBHOOK_PORT,
        reload=False,
        log_level="info"
    )