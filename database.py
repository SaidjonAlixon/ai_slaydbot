import sqlite3
import asyncio
import aiosqlite
from datetime import datetime
from typing import Dict, List, Optional, Any

DATABASE_PATH = "bot.db"

async def init_db():
    """Ma'lumotlar bazasini ishga tushirish"""
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Users jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT NOT NULL,
                phone TEXT,
                contact_shared BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Orders jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_tg_id INTEGER NOT NULL,
                topic TEXT NOT NULL,
                pages INTEGER NOT NULL,
                tariff TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (user_tg_id) REFERENCES users (tg_id)
            )
        """)
        
        # Presentations jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS presentations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_tg_id INTEGER NOT NULL,
                order_id INTEGER,
                topic TEXT NOT NULL,
                pages INTEGER NOT NULL,
                tariff TEXT NOT NULL,
                file_path TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_tg_id) REFERENCES users (tg_id),
                FOREIGN KEY (order_id) REFERENCES orders (id)
            )
        """)
        
        # Actions log jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS action_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_tg_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_tg_id) REFERENCES users (tg_id)
            )
        """)
        
        await db.commit()


async def get_user_by_tg_id(tg_id: int) -> Optional[Dict[str, Any]]:
    """Foydalanuvchini Telegram ID bo'yicha olish"""
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE tg_id = ?", 
            (tg_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def create_user(user_data: Dict[str, Any]) -> int:
    """Yangi foydalanuvchi yaratish"""
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO users (tg_id, username, full_name, phone, contact_shared)
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_data['tg_id'],
            user_data.get('username'),
            user_data['full_name'],
            user_data.get('phone'),
            user_data.get('contact_shared', False)
        ))
        await db.commit()
        return cursor.lastrowid


async def create_order(order_data: Dict[str, Any]) -> int:
    """Yangi buyurtma yaratish"""
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO orders (user_tg_id, topic, pages, tariff, status)
            VALUES (?, ?, ?, ?, ?)
        """, (
            order_data['user_tg_id'],
            order_data['topic'],
            order_data['pages'],
            order_data['tariff'],
            order_data.get('status', 'pending')
        ))
        await db.commit()
        return cursor.lastrowid


async def get_active_order(user_tg_id: int) -> Optional[Dict[str, Any]]:
    """Foydalanuvchining faol buyurtmasini olish"""
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM orders 
            WHERE user_tg_id = ? AND status IN ('pending', 'confirmed', 'processing')
            ORDER BY created_at DESC 
            LIMIT 1
        """, (user_tg_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_order_status(order_id: int, status: str) -> bool:
    """Buyurtma holatini yangilash"""
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            UPDATE orders 
            SET status = ?, completed_at = ?
            WHERE id = ?
        """, (
            status, 
            datetime.now().isoformat() if status in ['completed', 'failed'] else None,
            order_id
        ))
        await db.commit()
        return cursor.rowcount > 0


async def save_presentation(presentation_data: Dict[str, Any]) -> int:
    """Taqdimot ma'lumotlarini saqlash"""
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO presentations (user_tg_id, order_id, topic, pages, tariff, file_path, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            presentation_data['user_tg_id'],
            presentation_data.get('order_id'),
            presentation_data['topic'],
            presentation_data['pages'],
            presentation_data['tariff'],
            presentation_data.get('file_path'),
            presentation_data.get('status', 'completed')
        ))
        await db.commit()
        return cursor.lastrowid


async def save_slide(slide_data: Dict[str, Any]) -> int:
    """Slayd ma'lumotlarini saqlash"""
    
    # Hozircha slide jadvali yo'q, faqat presentation ga qo'shamiz
    return await save_presentation(slide_data)


async def log_action(user_tg_id: int, action: str, data: Optional[Dict[str, Any]] = None) -> int:
    """Foydalanuvchi harakatini log qilish"""
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO action_logs (user_tg_id, action, data)
            VALUES (?, ?, ?)
        """, (
            user_tg_id,
            action,
            str(data) if data else None
        ))
        await db.commit()
        
        # Foydalanuvchi faolligini yangilash
        await db.execute("""
            UPDATE users 
            SET last_activity = CURRENT_TIMESTAMP 
            WHERE tg_id = ?
        """, (user_tg_id,))
        await db.commit()
        
        return cursor.lastrowid


async def get_user_statistics(user_tg_id: int) -> Dict[str, Any]:
    """Foydalanuvchi statistikasini olish"""
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Umumiy taqdimotlar soni
        async with db.execute("""
            SELECT COUNT(*) as total FROM presentations 
            WHERE user_tg_id = ? AND status = 'completed'
        """, (user_tg_id,)) as cursor:
            total_presentations = (await cursor.fetchone())[0]
        
        # Bu oy taqdimotlar soni
        async with db.execute("""
            SELECT COUNT(*) as this_month FROM presentations 
            WHERE user_tg_id = ? AND status = 'completed'
            AND strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
        """, (user_tg_id,)) as cursor:
            this_month = (await cursor.fetchone())[0]
        
        # O'tgan oy taqdimotlar soni
        async with db.execute("""
            SELECT COUNT(*) as last_month FROM presentations 
            WHERE user_tg_id = ? AND status = 'completed'
            AND strftime('%Y-%m', created_at) = strftime('%Y-%m', date('now', '-1 month'))
        """, (user_tg_id,)) as cursor:
            last_month = (await cursor.fetchone())[0]
        
        # Faol kunlar soni
        async with db.execute("""
            SELECT COUNT(DISTINCT DATE(created_at)) as active_days 
            FROM action_logs 
            WHERE user_tg_id = ?
        """, (user_tg_id,)) as cursor:
            active_days = (await cursor.fetchone())[0]
        
        # So'nggi faollik
        async with db.execute("""
            SELECT MAX(last_activity) as last_activity 
            FROM users 
            WHERE tg_id = ?
        """, (user_tg_id,)) as cursor:
            last_activity = (await cursor.fetchone())[0]
        
        return {
            'total_presentations': total_presentations,
            'this_month': this_month,
            'last_month': last_month,
            'active_days': active_days,
            'last_activity': last_activity or 'Hali yo\'q'
        }


async def get_all_users() -> List[Dict[str, Any]]:
    """Barcha foydalanuvchilarni olish"""
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users ORDER BY created_at DESC") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_user_orders(user_tg_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Foydalanuvchi buyurtmalarini olish"""
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM orders 
            WHERE user_tg_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (user_tg_id, limit)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def cleanup_old_files():
    """Eski fayllarni tozalash"""
    
    import os
    import glob
    from datetime import datetime, timedelta
    
    # 7 kun oldin yaratilgan fayllarni o'chirish
    cutoff_date = datetime.now() - timedelta(days=7)
    
    # PPTX fayllarini topish
    pptx_files = glob.glob("slayd_*.pptx")
    
    for file_path in pptx_files:
        try:
            # Fayl yaratilish vaqtini olish
            file_time = datetime.fromtimestamp(os.path.getctime(file_path))
            
            if file_time < cutoff_date:
                os.remove(file_path)
                print(f"Eski fayl o'chirildi: {file_path}")
                
        except Exception as e:
            print(f"Fayl o'chirishda xatolik {file_path}: {e}")
