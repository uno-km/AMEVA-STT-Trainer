import sys
import os
import sqlite3

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.getcwd())

def clean():
    db_path = os.path.join(os.getcwd(), "db", "stt_trainer.db")
    if not os.path.exists(db_path):
        print(f"DB를 찾을 수 없습니다: {db_path}")
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # tb_task와 tb_task_dtl에서 RUNNING 상태인 모든 태스크를 FAILED로 변경
    cursor.execute("UPDATE tb_task SET status='FAILED' WHERE status='RUNNING'")
    cursor.execute("UPDATE tb_task_dtl SET status='FAILED' WHERE status='RUNNING'")
    
    changed = cursor.rowcount
    conn.commit()
    conn.close()
    print(f"성공: {changed}개의 유령 태스크를 정리했습니다.")

if __name__ == "__main__":
    clean()
