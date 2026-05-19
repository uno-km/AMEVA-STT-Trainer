import os
import sqlite3
from datetime import datetime

def sync():
    db_path = "db/stt_trainer.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Active task ID
    task_id = "e7f1f127-bf57-4eed-b3c4-2d8ef13dcb7e"
    
    # Check if task exists
    cursor.execute("SELECT id, tsk_nm FROM tb_task WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    if not task:
        print(f"Task {task_id} not found.")
        return
    print(f"Syncing logs for task: {task[1]} ({task[0]})")
    
    # Scan downloaded files
    path = "dataset/2026/05/19"
    if not os.path.exists(path):
        print("Directory does not exist.")
        return
        
    dirs = os.listdir(path)
    idx = 0
    for d in dirs:
        video_dir = os.path.join(path, d)
        audio_path = os.path.join(video_dir, "raw.wav")
        vtt_path = os.path.join(video_dir, f"{d}.ko.vtt")
        
        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
            size_mb = os.path.getsize(audio_path) / (1024 * 1024)
            folder_rel = os.path.relpath(video_dir, os.getcwd())
            create_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            
            # Log message
            msg = f"▶ [다운로드 완료] {idx+1} - 복원 성공: ID='{d}' | 용량: {size_mb:.2f}MB | 폴더: {folder_rel}"
            
            # Check if already logged
            cursor.execute("SELECT 1 FROM tb_log WHERE task_id = ? AND message LIKE ?", (task_id, f"%{d}%"))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO tb_log (task_id, level, message, create_dt) VALUES (?, ?, ?, ?)",
                    (task_id, "INFO", msg, create_dt)
                )
                print(f"Logged: {msg}")
                idx += 1
                
    conn.commit()
    conn.close()
    print("Retroactive log sync completed.")

if __name__ == "__main__":
    sync()
