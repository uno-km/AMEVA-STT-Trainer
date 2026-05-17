import sqlite3
import json

db_path = "db/stt_trainer.db"
task_id = "c408da91-a72d-433e-9fed-28c3348d95cf"

print(f"--- 태스크 ID: {task_id} DB 파라미터 정밀 분석 ---")
try:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # tb_task_dtl 조회
    cursor.execute("SELECT * FROM tb_task_dtl WHERE task_id = ?", (task_id,))
    rows = cursor.fetchall()
    
    for row in rows:
        print(f"\n[단계 {row['step_seq']}] {row['step_name']} (다음 단계: {row['next_step']})")
        print(f"상태: {row['status']}")
        try:
            params = json.loads(row['parameters'])
            print(f"저장된 파라미터 원문:")
            print(json.dumps(params, indent=2, ensure_ascii=False))
        except Exception as je:
            print(f"파라미터 파싱 실패: {je} (원문: {row['parameters']})")
            
except Exception as e:
    print(f"DB 조회 중 오류 발생: {e}")
finally:
    if 'conn' in locals():
        conn.close()
