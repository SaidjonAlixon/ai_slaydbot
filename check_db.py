import sqlite3

conn = sqlite3.connect('DataBase.db')
cursor = conn.cursor()

# Barcha jadvallarni ko'rish
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("Jadvallar:")
for table in tables:
    print(f"- {table[0]}")

# Har bir jadvalning strukturasini ko'rish
for table in tables:
    table_name = table[0]
    print(f"\n{table_name} jadvali:")
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    for col in columns:
        print(f"  {col[1]} - {col[2]}")

conn.close()
