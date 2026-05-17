import sqlite3

def fix_db():
    conn = sqlite3.connect("db/stt_trainer.db")
    cursor = conn.cursor()
    
    # 현재 'RUNNING' 상태로 유령 동결된 모든 태스크 조회
    cursor.execute("SELECT id, tsk_nm, level FROM tb_task WHERE status='RUNNING';")
    running = cursor.fetchall()
    print(f"Running Tasks: {running}")
    
    if running:
        for task_id, name, level in running:
            print(f"Task {name} ({task_id}) - Level {level} fixing...")
            
            # 태스크 최종 상태를 FAILED로 안전 갱신 (기존 단계 레벨은 정확히 유지!)
            cursor.execute(
                "UPDATE tb_task SET status='FAILED' WHERE id=?;",
                (task_id,)
            )
            
            # 진행 상태 상세정보 테이블도 정합성에 맞게 갱신
            cursor.execute(
                "UPDATE tb_task_dtl SET status='FAILED' WHERE task_id=? AND status='RUNNING';",
                (task_id,)
            )
            
            # 로그에 강제 동기화 복구 흔적 기록
            cursor.execute(
                "INSERT INTO tb_log (task_id, level, message, create_dt) VALUES (?, 'ERROR', ?, datetime('now', 'localtime'));",
                (task_id, "Status reset by system recovery tool.")
            )
            
        conn.commit()
        print("Success: All frozen tasks have been updated to FAILED status.")
    else:
        print("All clean. No frozen RUNNING tasks detected.")
        
    conn.close()

if __name__ == "__main__":
    fix_db()
