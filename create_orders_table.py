import sqlite3

conn = sqlite3.connect('DataBase.db')
cursor = conn.cursor()

# Orders jadvalini yaratish
cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_tg_id INTEGER NOT NULL,
    tariff TEXT NOT NULL,
    topic TEXT NOT NULL,
    slides_count INTEGER NOT NULL,
    design_style TEXT,
    color_scheme TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (user_tg_id) REFERENCES users (user_id)
)
""")

conn.commit()
print("Orders jadvali yaratildi!")

conn.close()
