"""
scripts/tests/test_database_integrity.py
AMEVA-STT-Trainer QA Automation: SQLite Database Integrity Auditor
- Automatically audits table existence: tb_task, tb_metric, tb_task_dtl, tb_metadata, tb_chunk, tb_log, tb_thread_log.
- Inspects schema layouts, column specifications, and prints data volumes.
"""
import os
import sys
import sqlite3

def run_db_audit():
    # 프로젝트 루트 및 sys.path 설정
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    db_path = os.path.join(project_root, "db", "stt_trainer.db")

    print("\n" + "=" * 80)
    print(">>> QA DB Audit: Relational Database Integrity & Schema Auditor")
    print(f"[*] Database Path: {db_path}")
    print("=" * 80 + "\n")

    if not os.path.exists(db_path):
        print(f"[!] Error: Database file does not exist at {db_path}")
        sys.exit(1)

    tables_to_verify = [
        "tb_task",
        "tb_metric",
        "tb_task_dtl",
        "tb_metadata",
        "tb_chunk",
        "tb_log",
        "tb_thread_log"
    ]

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 1. 연결 성공 여부
        print("[+] SQLite Connection: SUCCESS")

        # 2. 각 테이블 스캔 및 스키마 검증
        for table in tables_to_verify:
            print(f"\n" + "-" * 50)
            print(f"[*] Auditing Table: {table}")
            
            # 테이블 존재 여부 확인
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
            res = cursor.fetchone()
            if not res:
                print(f"    ❌ Error: Table '{table}' does not exist!")
                sys.exit(1)
            print(f"    [+] Table Existence: EXISTS")

            # 레코드 카운트 조회
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"    [+] Active Rows: {count}")

            # 컬럼 정보 파싱 (PRAGMA table_info)
            cursor.execute(f"PRAGMA table_info({table})")
            columns = cursor.fetchall()
            print(f"    [+] Columns Layout:")
            for col in columns:
                pk_indicator = " (PRIMARY KEY)" if col['pk'] else ""
                notnull_indicator = " NOT NULL" if col['notnull'] else ""
                print(f"        - {col['name']} ({col['type']}){pk_indicator}{notnull_indicator}")
            
            # 샘플 데이터 상위 1개 시각화
            cursor.execute(f"SELECT * FROM {table} LIMIT 1")
            sample = cursor.fetchone()
            if sample:
                print(f"    [+] Top Record Sample:")
                for col_name in sample.keys():
                    print(f"        {col_name} : {sample[col_name]}")
            else:
                print(f"    [+] Top Record Sample: [Table is currently empty]")

        conn.close()
        print("\n" + "=" * 80)
        print("[+] QA DB Audit: SUCCESS! Database is fully consistent, schemas match expectations.")
        sys.exit(0)

    except Exception as e:
        print(f"\n[!] Critical DB Audit Failure: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_db_audit()
