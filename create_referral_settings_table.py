import sqlite3

conn = sqlite3.connect('DataBase.db')
cursor = conn.cursor()

# Referral settings jadvalini yaratish
cursor.execute("""
CREATE TABLE IF NOT EXISTS referral_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    referrer_reward INTEGER DEFAULT 1000,
    referred_reward INTEGER DEFAULT 500,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Agar jadval bo'sh bo'lsa, default qiymatlarni qo'shish
cursor.execute("SELECT COUNT(*) FROM referral_settings")
count = cursor.fetchone()[0]

if count == 0:
    cursor.execute("""
        INSERT INTO referral_settings (referrer_reward, referred_reward) 
        VALUES (1000, 500)
    """)

conn.commit()
print("Referral settings jadvali yaratildi va default qiymatlar qo'shildi!")

conn.close()
