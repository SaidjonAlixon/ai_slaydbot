import sqlite3
import asyncio
import aiosqlite
import os
from datetime import datetime
from typing import Dict, List, Optional, Any

# Mavjud DataBase.db faylini ishlatish
DATABASE_PATH = os.getenv("DATABASE_PATH", "DataBase.db")

async def get_user_by_tg_id(tg_id: int) -> Optional[Dict[str, Any]]:
    """Foydalanuvchini Telegram ID bo'yicha olish (mavjud database strukturasiga mos)"""
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE user_id = ?", (str(tg_id),)
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
        
        # Agar user_id ustunida topilmasa, boshqa ustunlarni ham tekshirish
        # DataBase.db faylida faqat user_id ustuni mavjud
        return None

async def create_user(user_data: Dict[str, Any]) -> int:
    """Yangi foydalanuvchi yaratish (mavjud database strukturasiga mos)"""
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO users (user_id, lang, name, phone_number, order_type, order_name, order_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            str(user_data['tg_id']),
            user_data.get('lang', 'uz'),
            user_data.get('full_name', user_data.get('name', 'Foydalanuvchi')),
            user_data.get('phone', ''),
            'False',
            'False',
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
        await db.commit()
        return cursor.lastrowid

async def get_all_users() -> List[Dict[str, Any]]:
    """Barcha foydalanuvchilarni olish"""
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users ORDER BY order_date DESC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def get_users_count() -> int:
    """Foydalanuvchilar sonini olish"""
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        result = await cursor.fetchone()
        return result[0] if result else 0

async def search_users(query: str) -> List[Dict[str, Any]]:
    """Foydalanuvchilarni qidirish"""
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM users 
            WHERE name LIKE ? OR user_id LIKE ? OR phone_number LIKE ?
            ORDER BY order_date DESC
        """, (f"%{query}%", f"%{query}%", f"%{query}%"))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def init_db():
    """Ma'lumotlar bazasini ishga tushirish (faqat mavjud DataBase.db ishlatish)"""
    
    if not os.path.exists(DATABASE_PATH):
        print(f"Database fayli topilmadi: {DATABASE_PATH}")
        print("Iltimos, DataBase.db faylini loyiha papkasiga qo'ying!")
        return
    
    print(f"Database yuklandi: {DATABASE_PATH}")
    
    # Foydalanuvchilar sonini ko'rsatish
    user_count = await get_users_count()
    print(f"Jami foydalanuvchilar soni: {user_count}")
    
    # Agar foydalanuvchilar bo'lsa, bir nechtasini ko'rsatish
    if user_count > 0:
        users = await get_all_users()
        print(f"Oxirgi 5 ta foydalanuvchi:")
        for i, user in enumerate(users[:5], 1):
            # Unicode belgilarni to'g'ri ko'rsatish
            try:
                name = user['name']
                phone = user['phone_number']
                print(f"  {i}. ID: {user['user_id']}, Ism: {name}, Telefon: {phone}")
            except UnicodeEncodeError:
                # Agar Unicode xatolik bo'lsa, oddiy matn ko'rsatish
                name = str(user['name']).encode('ascii', errors='ignore').decode('ascii')
                phone = str(user['phone_number']).encode('ascii', errors='ignore').decode('ascii')
                print(f"  {i}. ID: {user['user_id']}, Ism: {name}, Telefon: {phone}")

# Boshqa funksiyalar uchun placeholder'lar
async def create_order(order_data: Dict[str, Any]) -> int:
    return 0

async def get_active_order(user_tg_id: int) -> Optional[Dict[str, Any]]:
    return None

async def update_order_status(order_id: int, status: str):
    pass

async def log_action(user_tg_id: int, action: str, data: Dict[str, Any]):
    pass

async def save_presentation(presentation_data: Dict[str, Any]) -> int:
    return 0

async def save_slide(slide_data: Dict[str, Any]) -> int:
    return 0

async def get_user_statistics(user_tg_id: int) -> Dict[str, Any]:
    return {}

async def get_user_balance(user_tg_id: int) -> Dict[str, Any]:
    return {"total_balance": 0, "cash_balance": 0, "referral_balance": 0}

async def update_user_balance(user_tg_id: int, balance_data: Dict[str, Any]):
    pass

async def deduct_user_balance(user_tg_id: int, amount: int) -> bool:
    return True

async def create_referral(referrer_tg_id: int, referred_tg_id: int):
    pass

async def confirm_referral(referrer_tg_id: int, referred_tg_id: int):
    pass

async def get_referral_stats(user_tg_id: int) -> Dict[str, Any]:
    return {
        'confirmed_referrals': 0,
        'total_referrals': 0,
        'referral_earnings': 0
    }

async def get_user_free_orders_count(user_tg_id: int) -> int:
    return 0

async def add_transaction(transaction_data: Dict[str, Any]) -> int:
    return 0

async def get_referral_rewards(user_tg_id: int) -> List[Dict[str, Any]]:
    return []

async def update_referral_rewards(referrer_amount: int, referred_amount: int):
    pass
