import sqlite3
import asyncio
import aiosqlite
import os
from datetime import datetime
from typing import Dict, List, Optional, Any

# Railway'da persistent volume, local'da mavjud DataBase.db ishlatish
DATABASE_PATH = os.getenv("DATABASE_PATH", "DataBase.db")

async def init_db():
    """Ma'lumotlar bazasini ishga tushirish"""
    
    # Railway'da persistent volume uchun papka yaratish
    if DATABASE_PATH != "bot.db":
        db_dir = os.path.dirname(DATABASE_PATH)
        os.makedirs(db_dir, exist_ok=True)
        print(f"Database directory created: {db_dir}")
    
    # SQLite ishlatish (Railway'da ham)
    print(f"Connecting to database: {DATABASE_PATH}")
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
        
        # User balances jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_balances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_tg_id INTEGER UNIQUE NOT NULL,
                total_balance INTEGER DEFAULT 0,
                cash_balance INTEGER DEFAULT 0,
                referral_balance INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_tg_id) REFERENCES users (tg_id)
            )
        """)
        
        # Referral system jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_tg_id INTEGER NOT NULL,
                referred_tg_id INTEGER UNIQUE NOT NULL,
                bonus_earned INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confirmed_at TIMESTAMP,
                FOREIGN KEY (referrer_tg_id) REFERENCES users (tg_id),
                FOREIGN KEY (referred_tg_id) REFERENCES users (tg_id)
            )
        """)
        
        # Payment transactions jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_tg_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                transaction_type TEXT NOT NULL,
                description TEXT,
                order_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_tg_id) REFERENCES users (tg_id),
                FOREIGN KEY (order_id) REFERENCES orders (id)
            )
        """)
        
        # Admin settings jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admin_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                setting_key TEXT UNIQUE NOT NULL,
                setting_value TEXT NOT NULL,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Default referral settings qo'shish
        await db.execute("""
            INSERT OR IGNORE INTO admin_settings (setting_key, setting_value, description)
            VALUES 
                ('referral_reward_referrer', '1000', 'Taklif qilgan foydalanuvchi uchun bonus'),
                ('referral_reward_referred', '500', 'Taklif qilingan foydalanuvchi uchun bonus')
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


# Balans funksiyalari
async def get_user_balance(user_tg_id: int) -> Dict[str, int]:
    """Foydalanuvchi balansini olish"""
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM user_balances WHERE user_tg_id = ?
        """, (user_tg_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            else:
                # Agar balans yo'q bo'lsa, yangi yaratish
                await db.execute("""
                    INSERT INTO user_balances (user_tg_id, total_balance, cash_balance, referral_balance)
                    VALUES (?, 0, 0, 0)
                """, (user_tg_id,))
                await db.commit()
                return {
                    'user_tg_id': user_tg_id,
                    'total_balance': 0,
                    'cash_balance': 0,
                    'referral_balance': 0
                }


async def update_user_balance(user_tg_id: int, amount: int, balance_type: str = 'cash') -> bool:
    """Foydalanuvchi balansini yangilash"""
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Balans mavjudligini tekshirish
        async with db.execute("""
            SELECT id FROM user_balances WHERE user_tg_id = ?
        """, (user_tg_id,)) as cursor:
            row = await cursor.fetchone()
            
            if not row:
                # Yangi balans yaratish
                await db.execute("""
                    INSERT INTO user_balances (user_tg_id, total_balance, cash_balance, referral_balance)
                    VALUES (?, ?, ?, ?)
                """, (user_tg_id, amount, amount if balance_type == 'cash' else 0, amount if balance_type == 'referral' else 0))
            else:
                # Mavjud balansni yangilash
                if balance_type == 'cash':
                    await db.execute("""
                        UPDATE user_balances 
                        SET cash_balance = cash_balance + ?, 
                            total_balance = total_balance + ?,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE user_tg_id = ?
                    """, (amount, amount, user_tg_id))
                elif balance_type == 'referral':
                    await db.execute("""
                        UPDATE user_balances 
                        SET referral_balance = referral_balance + ?, 
                            total_balance = total_balance + ?,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE user_tg_id = ?
                    """, (amount, amount, user_tg_id))
        
        await db.commit()
        return True


async def deduct_user_balance(user_tg_id: int, amount: int) -> bool:
    """Foydalanuvchi balansidan mablag' yechish"""
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Balans yetarli ekanligini tekshirish
        balance = await get_user_balance(user_tg_id)
        if balance['total_balance'] < amount:
            return False
            
        await db.execute("""
            UPDATE user_balances 
            SET total_balance = total_balance - ?,
                last_updated = CURRENT_TIMESTAMP
            WHERE user_tg_id = ?
        """, (amount, user_tg_id))
        await db.commit()
        return True


# Referral funksiyalari
async def create_referral(referrer_tg_id: int, referred_tg_id: int) -> bool:
    """Yangi referral yaratish"""
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute("""
                INSERT INTO referrals (referrer_tg_id, referred_tg_id, status)
                VALUES (?, ?, 'pending')
            """, (referrer_tg_id, referred_tg_id))
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            # Agar referral allaqachon mavjud bo'lsa
            return False


async def confirm_referral(referred_tg_id: int) -> bool:
    """Referralni tasdiqlash va bonus berish"""
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Referralni topish
        async with db.execute("""
            SELECT referrer_tg_id FROM referrals 
            WHERE referred_tg_id = ? AND status = 'pending'
        """, (referred_tg_id,)) as cursor:
            row = await cursor.fetchone()
            
            if not row:
                return False
                
            referrer_tg_id = row[0]
            
            # Referral bonuslarini olish
            rewards = await get_referral_rewards()
            referrer_reward = rewards['referrer_reward']
            referred_reward = rewards['referred_reward']
            
            # Referralni tasdiqlash
            await db.execute("""
                UPDATE referrals 
                SET status = 'confirmed', 
                    bonus_earned = ?,
                    confirmed_at = CURRENT_TIMESTAMP
                WHERE referred_tg_id = ?
            """, (referrer_reward, referred_tg_id))
            
            # Referrer ga bonus berish
            await update_user_balance(referrer_tg_id, referrer_reward, 'referral')
            
            # Referred user ga ham bonus berish
            await update_user_balance(referred_tg_id, referred_reward, 'referral')
            
            await db.commit()
            return True


async def get_referral_stats(user_tg_id: int) -> Dict[str, Any]:
    """Referral statistikasini olish"""
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Umumiy referrallar soni
        async with db.execute("""
            SELECT COUNT(*) as total FROM referrals WHERE referrer_tg_id = ?
        """, (user_tg_id,)) as cursor:
            total_referrals = (await cursor.fetchone())[0]
        
        # Tasdiqlangan referrallar soni
        async with db.execute("""
            SELECT COUNT(*) as confirmed FROM referrals 
            WHERE referrer_tg_id = ? AND status = 'confirmed'
        """, (user_tg_id,)) as cursor:
            confirmed_referrals = (await cursor.fetchone())[0]
        
        # Jami bonus
        async with db.execute("""
            SELECT SUM(bonus_earned) as total_bonus FROM referrals 
            WHERE referrer_tg_id = ? AND status = 'confirmed'
        """, (user_tg_id,)) as cursor:
            total_bonus = (await cursor.fetchone())[0] or 0
        
        # Bu oy referrallar
        async with db.execute("""
            SELECT COUNT(*) as this_month FROM referrals 
            WHERE referrer_tg_id = ? AND strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
        """, (user_tg_id,)) as cursor:
            this_month = (await cursor.fetchone())[0]
        
        return {
            'total_referrals': total_referrals,
            'confirmed_referrals': confirmed_referrals,
            'pending_referrals': total_referrals - confirmed_referrals,
            'total_bonus': total_bonus,
            'this_month': this_month
        }


async def get_user_free_orders_count(user_tg_id: int) -> int:
    """Foydalanuvchining bepul buyurtmalar sonini olish (START tarifi uchun)"""
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("""
            SELECT COUNT(*) FROM presentations 
            WHERE user_tg_id = ? AND tariff = 'START' AND status = 'completed'
        """, (user_tg_id,)) as cursor:
            return (await cursor.fetchone())[0]


async def add_transaction(user_tg_id: int, amount: int, transaction_type: str, description: str = None, order_id: int = None) -> int:
    """Tranzaksiya qo'shish"""
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO transactions (user_tg_id, amount, transaction_type, description, order_id)
            VALUES (?, ?, ?, ?, ?)
        """, (user_tg_id, amount, transaction_type, description, order_id))
        await db.commit()
        return cursor.lastrowid


# Admin settings funksiyalari
async def get_admin_setting(setting_key: str, default_value: str = None) -> str:
    """Admin sozlamasini olish"""
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("""
            SELECT setting_value FROM admin_settings WHERE setting_key = ?
        """, (setting_key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default_value


async def update_admin_setting(setting_key: str, setting_value: str, description: str = None) -> bool:
    """Admin sozlamasini yangilash"""
    
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("""
            INSERT OR REPLACE INTO admin_settings (setting_key, setting_value, description, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (setting_key, setting_value, description))
        await db.commit()
        return cursor.rowcount > 0


async def get_referral_rewards() -> Dict[str, int]:
    """Referral bonuslarini olish"""
    
    referrer_reward = await get_admin_setting('referral_reward_referrer', '1000')
    referred_reward = await get_admin_setting('referral_reward_referred', '500')
    
    return {
        'referrer_reward': int(referrer_reward),
        'referred_reward': int(referred_reward)
    }


async def update_referral_rewards(referrer_reward: int, referred_reward: int) -> bool:
    """Referral bonuslarini yangilash"""
    
    try:
        await update_admin_setting(
            'referral_reward_referrer', 
            str(referrer_reward), 
            'Taklif qilgan foydalanuvchi uchun bonus'
        )
        await update_admin_setting(
            'referral_reward_referred', 
            str(referred_reward), 
            'Taklif qilingan foydalanuvchi uchun bonus'
        )
        return True
    except Exception:
        return False


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
