import sqlite3

def check_db():
    conn = sqlite3.connect("db/stt_trainer.db")
    cursor = conn.cursor()
    
    # 1. 테이블 목록 확인
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"Tables: {tables}")
    
    for table in tables:
        table_name = table[0]
        print(f"\n--- Schema for {table_name} ---")
        cursor.execute(f"PRAGMA table_info({table_name});")
        info = cursor.fetchall()
        for col in info:
            print(col)
            
    conn.close()

if __name__ == "__main__":
    check_db()
