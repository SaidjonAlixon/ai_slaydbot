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
        # Foydalanuvchini users jadvaliga qo'shish
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
        
        # Balans jadvaliga ham qo'shish
        await db.execute("""
            INSERT INTO user_balances (user_id, cash_balance, referral_balance, total_balance, created_at, updated_at)
            VALUES (?, 0, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (str(user_data['tg_id']),))
        
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
    """Foydalanuvchi balansini olish"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute(
                "SELECT cash_balance, referral_balance, total_balance FROM user_balances WHERE user_id = ?", (str(user_tg_id),)
            )
            row = await cursor.fetchone()
            
            if row:
                return {
                    "total_balance": row[2] or 0,
                    "cash_balance": row[0] or 0,
                    "referral_balance": row[1] or 0
                }
            else:
                return {"total_balance": 0, "cash_balance": 0, "referral_balance": 0}
                
    except Exception as e:
        print(f"Balans olishda xatolik: {e}")
        return {"total_balance": 0, "cash_balance": 0, "referral_balance": 0}

async def update_user_balance(user_tg_id: int, amount: int, balance_type: str = 'cash'):
    """Foydalanuvchi balansini yangilash"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Foydalanuvchini topish
            cursor = await db.execute(
                "SELECT * FROM users WHERE user_id = ?", (str(user_tg_id),)
            )
            user = await cursor.fetchone()
            
            if not user:
                return False
            
            # Balansni yangilash
            if balance_type == 'cash':
                await db.execute(
                    "UPDATE user_balances SET cash_balance = cash_balance + ?, total_balance = total_balance + ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?", 
                    (amount, amount, str(user_tg_id))
                )
            elif balance_type == 'referral':
                await db.execute(
                    "UPDATE user_balances SET referral_balance = referral_balance + ?, total_balance = total_balance + ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?", 
                    (amount, amount, str(user_tg_id))
                )
            
            await db.commit()
            return True
            
    except Exception as e:
        print(f"Balans yangilashda xatolik: {e}")
        return False

async def deduct_user_balance(user_tg_id: int, amount: int) -> bool:
    """Foydalanuvchi balansidan ayirish"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Foydalanuvchini topish
            cursor = await db.execute(
                "SELECT total_balance FROM user_balances WHERE user_id = ?", (str(user_tg_id),)
            )
            row = await cursor.fetchone()
            
            if not row:
                return False
            
            current_balance = row[0] or 0
            
            # Balans yetarli emas
            if current_balance < amount:
                return False
            
            # Balansdan ayirish (naqt balansdan)
            await db.execute(
                "UPDATE user_balances SET cash_balance = cash_balance - ?, total_balance = total_balance - ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?", 
                (amount, amount, str(user_tg_id))
            )
            await db.commit()
            return True
            
    except Exception as e:
        print(f"Balans ayirishda xatolik: {e}")
        return False

async def create_referral(referrer_tg_id: int, referred_tg_id: int) -> bool:
    """Referral yaratish"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute(
                "INSERT INTO referrals (referrer_id, referred_id, status) VALUES (?, ?, 'pending')",
                (str(referrer_tg_id), str(referred_tg_id))
            )
            await db.commit()
            return True
    except Exception as e:
        print(f"Referral yaratishda xatolik: {e}")
        return False

async def confirm_referral(referrer_tg_id: int, referred_tg_id: int) -> bool:
    """Referralni tasdiqlash"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Referralni tasdiqlash
            await db.execute(
                "UPDATE referrals SET status = 'confirmed', confirmed_at = CURRENT_TIMESTAMP WHERE referrer_id = ? AND referred_id = ?",
                (str(referrer_tg_id), str(referred_tg_id))
            )
            
            # Bonuslarni qo'shish
            rewards = await get_referral_rewards()
            
            # Taklif qiluvchiga bonus
            await update_user_balance(referrer_tg_id, rewards['referrer_reward'], 'referral')
            
            # Taklif qilinganga bonus
            await update_user_balance(referred_tg_id, rewards['referred_reward'], 'referral')
            
            await db.commit()
            return True
    except Exception as e:
        print(f"Referral tasdiqlashda xatolik: {e}")
        return False

async def get_referral_stats(user_tg_id: int) -> Dict[str, Any]:
    """Foydalanuvchining referral statistikasini olish"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            
            # Referral statistikasini olish
            cursor = await db.execute(
                "SELECT COUNT(*) as total FROM referrals WHERE referrer_id = ?", 
                (str(user_tg_id),)
            )
            total_referrals = (await cursor.fetchone())['total'] or 0
            
            cursor = await db.execute(
                "SELECT COUNT(*) as confirmed FROM referrals WHERE referrer_id = ? AND status = 'confirmed'", 
                (str(user_tg_id),)
            )
            confirmed_referrals = (await cursor.fetchone())['confirmed'] or 0
            
            # Referral balansini olish
            balance = await get_user_balance(user_tg_id)
            referral_earnings = balance['referral_balance']
            
            return {
                'total_referrals': total_referrals,
                'confirmed_referrals': confirmed_referrals,
                'pending_referrals': total_referrals - confirmed_referrals,
                'total_bonus': referral_earnings,
                'this_month': 0  # Hozircha oddiy
            }
    except Exception as e:
        print(f"Referral statistikasini olishda xatolik: {e}")
        return {
            'total_referrals': 0,
            'confirmed_referrals': 0,
            'pending_referrals': 0,
            'total_bonus': 0,
            'this_month': 0
        }

async def get_user_free_orders_count(user_tg_id: int) -> int:
    """Foydalanuvchining bepul buyurtmalar sonini olish"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT COUNT(*) as count FROM orders WHERE user_tg_id = ? AND tariff = 'START' AND status = 'completed'",
            (user_tg_id,)
        )
        row = await cursor.fetchone()
        return row['count'] if row else 0

async def add_transaction(user_tg_id: int, amount: int, transaction_type: str, description: str, order_id: int = None) -> int:
    """Tranzaksiya qo'shish"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute(
                "INSERT INTO transactions (user_id, amount, transaction_type, description) VALUES (?, ?, ?, ?)",
                (str(user_tg_id), amount, transaction_type, description)
            )
            await db.commit()
            return cursor.lastrowid
    except Exception as e:
        print(f"Tranzaksiya qo'shishda xatolik: {e}")
        return 0

async def get_referral_rewards() -> Dict[str, int]:
    """Referral bonuslarini olish"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute(
                "SELECT referrer_reward, referred_reward FROM referral_settings ORDER BY id DESC LIMIT 1"
            )
            row = await cursor.fetchone()
            
            if row:
                return {
                    'referrer_reward': row[0],
                    'referred_reward': row[1]
                }
            else:
                # Agar jadval bo'sh bo'lsa, default qiymatlarni qaytarish
                return {
                    'referrer_reward': 1000,
                    'referred_reward': 500
                }
    except Exception as e:
        print(f"Referral bonuslarini olishda xatolik: {e}")
        return {
            'referrer_reward': 1000,
            'referred_reward': 500
        }

async def update_referral_rewards(referrer_amount: int, referred_amount: int) -> bool:
    """Referral bonuslarini yangilash"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Yangi qator qo'shish
            await db.execute(
                "INSERT INTO referral_settings (referrer_reward, referred_reward, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (referrer_amount, referred_amount)
            )
            await db.commit()
            print(f"Referral bonuslar yangilandi: taklif qilgan={referrer_amount}, taklif qilingan={referred_amount}")
            return True
    except Exception as e:
        print(f"Referral bonuslarini yangilashda xatolik: {e}")
        return False

async def create_order(order_data: Dict[str, Any]) -> int:
    """Yangi buyurtma yaratish"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute(
                """INSERT INTO orders (
                    user_tg_id, tariff, topic, slides_count, 
                    design_style, color_scheme, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (
                    order_data['user_tg_id'],
                    order_data['tariff'],
                    order_data['topic'],
                    order_data['slides_count'],
                    order_data['design_style'],
                    order_data['color_scheme'],
                    order_data['status']
                )
            )
            await db.commit()
            return cursor.lastrowid
    except Exception as e:
        print(f"Buyurtma yaratishda xatolik: {e}")
        return 0

async def update_order_status(order_id: int, status: str) -> bool:
    """Buyurtma holatini yangilash"""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            if status == 'completed':
                await db.execute(
                    "UPDATE orders SET status = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (status, order_id)
                )
            else:
                await db.execute(
                    "UPDATE orders SET status = ? WHERE id = ?",
                    (status, order_id)
                )
            await db.commit()
            print(f"Buyurtma holati yangilandi: ID={order_id}, Status={status}")
            return True
    except Exception as e:
        print(f"Buyurtma holatini yangilashda xatolik: {e}")
        return False

async def save_presentation(presentation_data: Dict[str, Any]) -> bool:
    """Taqdimot ma'lumotlarini saqlash"""
    try:
        # Bu funksiya taqdimot ma'lumotlarini saqlash uchun ishlatiladi
        # Hozircha faqat log qilamiz
        print(f"Taqdimot saqlandi: {presentation_data}")
        return True
    except Exception as e:
        print(f"Taqdimot saqlashda xatolik: {e}")
        return False
