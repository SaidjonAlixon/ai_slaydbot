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

# Logging o'chirilgan - print ishlatamiz
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )
# logger = logging.getLogger(__name__)

# Environment o'zgaruvchilar
BOT_TOKEN = os.getenv("BOT_TOKEN")

# FastAPI app yaratish
app = FastAPI(title="Telegram Bot API", version="1.0.0")

@app.on_event("startup")
async def startup_event():
    """FastAPI startup event"""
    print("FastAPI application started")

@app.get("/health")
async def health_check():
    """Healthcheck endpoint Railway uchun"""
    return {"status": "healthy"}

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
        print("Database initialized successfully")
        
        # Webhookni to'liq o'chirish (agar avval o'rnatilgan bo'lsa)
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            print("Webhook deleted successfully")
            
            # Webhook holatini tekshirish
            webhook_info = await bot.get_webhook_info()
            if webhook_info.url:
                print(f"Webhook hali ham faol: {webhook_info.url}")
                # Qo'shimcha urinish
                await bot.delete_webhook(drop_pending_updates=True)
                print("Webhook qaytadan o'chirildi")
            else:
                print("Webhook to'liq o'chirildi")
                
        except Exception as e:
            print(f"Webhook o'chirishda xatolik: {e}")
        
        print("Starting services...")
        
        # FastAPI server'ni ishga tushirish
        port = int(os.getenv("PORT", 8000))
        print(f"Starting FastAPI server on port {port}")
        
        # FastAPI server'ni avval to'liq ishga tushirish
        config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
        server = uvicorn.Server(config)
        
        # FastAPI server'ni background'da ishga tushirish
        async def run_fastapi():
            try:
                print("FastAPI server starting...")
                await server.serve()
            except Exception as e:
                print(f"FastAPI server xatoligi: {e}")
                raise
        
        # Bot polling'ni background task sifatida ishga tushirish
        async def run_bot_polling():
            try:
                # FastAPI server ishga tushish uchun kutish
                print("Waiting for FastAPI server to start...")
                await asyncio.sleep(5)  # Railway uchun ko'proq vaqt
                print("Bot polling boshlanmoqda...")
                
                # Webhook'ni to'liq o'chirish
                try:
                    await bot.delete_webhook(drop_pending_updates=True)
                    print("Webhook to'liq o'chirildi")
                except Exception as e:
                    print(f"Webhook o'chirishda xatolik: {e}")
                
                # Bot polling'ni ishga tushirish
                await dp.start_polling(bot)
            except Exception as e:
                print(f"Bot polling xatoligi: {e}")
        
        # Railway uchun optimallashtirilgan ishga tushirish
        print("Creating FastAPI task...")
        fastapi_task = asyncio.create_task(run_fastapi())
        
        # FastAPI server ishga tushish uchun kutish
        print("Waiting for FastAPI server to initialize...")
        await asyncio.sleep(8)  # Railway uchun ko'proq vaqt kutish
        print("FastAPI server should be ready, starting bot polling...")
        
        # Bot polling'ni ishga tushirish
        bot_task = asyncio.create_task(run_bot_polling())
        
        print("All services started successfully")
        print("Bot va FastAPI server ishga tushdi!")
        
        # Railway uchun - ikkala task'ni parallel ishga tushirish
        await asyncio.gather(fastapi_task, bot_task, return_exceptions=True)
        
    except Exception as e:
        print(f"Bot ishga tushishda xatolik: {e}")
        print(f"Xatolik: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())