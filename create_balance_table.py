import sqlite3

conn = sqlite3.connect('DataBase.db')
cursor = conn.cursor()

# Balans jadvalini yaratish
cursor.execute("""
CREATE TABLE IF NOT EXISTS user_balances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    cash_balance INTEGER DEFAULT 0,
    referral_balance INTEGER DEFAULT 0,
    total_balance INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
)
""")

# Balans jadvalini yaratish
cursor.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    amount INTEGER NOT NULL,
    transaction_type TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
)
""")

# Orders jadvalini yaratish
cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_tg_id INTEGER NOT NULL,
    topic TEXT,
    pages INTEGER,
    tariff TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_tg_id) REFERENCES users (user_id)
)
""")

conn.commit()
print("Jadvallar yaratildi!")

# Mavjud foydalanuvchilar uchun balans yaratish
cursor.execute("SELECT user_id FROM users")
users = cursor.fetchall()

for user in users:
    user_id = user[0]
    # Foydalanuvchi uchun balans yaratish
    cursor.execute("""
        INSERT OR IGNORE INTO user_balances (user_id, cash_balance, referral_balance, total_balance)
        VALUES (?, 0, 0, 0)
    """, (user_id,))

conn.commit()
print(f"{len(users)} ta foydalanuvchi uchun balans yaratildi!")

conn.close()
