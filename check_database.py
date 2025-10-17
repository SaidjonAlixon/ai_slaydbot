import sqlite3
import os

def check_database():
    db_path = "DataBase.db"
    if not os.path.exists(db_path):
        print(f"Database fayli topilmadi: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Jadval nomlarini olish
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print("Mavjud jadvallar:")
        for table in tables:
            print(f"  - {table[0]}")
        
        # Users jadvalini tekshirish
        if ('users',) in tables:
            # Jadval strukturasini ko'rish
            cursor.execute("PRAGMA table_info(users)")
            columns = cursor.fetchall()
            print("\nUsers jadvali ustunlari:")
            for col in columns:
                print(f"  - {col[1]} ({col[2]})")
            
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            print(f"\nFoydalanuvchilar soni: {user_count}")
            
            if user_count > 0:
                # Barcha ustunlarni olish
                cursor.execute("SELECT * FROM users LIMIT 5")
                users = cursor.fetchall()
                print("\nBirinchi 5 ta foydalanuvchi:")
                for i, user in enumerate(users, 1):
                    print(f"  {i}. {user}")
        
        conn.close()
        
    except Exception as e:
        print(f"Xatolik: {e}")

if __name__ == "__main__":
    check_database()