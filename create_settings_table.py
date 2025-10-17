import asyncio
import aiosqlite

DATABASE_PATH = "DataBase.db"

async def create_settings_table():
    """Sozlamalar jadvalini yaratish"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Sozlamalar jadvalini yaratish
            await db.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Presentation enabled sozlamasini qo'shish
            await db.execute("""
                INSERT OR REPLACE INTO settings (key, value, description)
                VALUES ('presentation_enabled', 'true', 'Taqdimot tayyorlash funksiyasi yoqilgan/yoki o''chirilgan')
            """)
            
            await db.commit()
            print("Sozlamalar jadvali yaratildi va presentation_enabled sozlamasi qoshildi")
            
    except Exception as e:
        print(f"Xatolik: {e}")

if __name__ == "__main__":
    asyncio.run(create_settings_table())
