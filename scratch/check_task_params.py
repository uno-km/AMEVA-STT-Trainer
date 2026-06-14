import sqlite3
import json

conn = sqlite3.connect("db/stt_trainer.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get the latest task
cursor.execute("SELECT * FROM tb_task ORDER BY create_dt DESC LIMIT 1")
task = cursor.fetchone()

if not task:
    print("NO_TASK")
else:
    print("=== TASK INFO ===")
    print(f"ID: {task['id']}")
    print(f"Name: {task['tsk_nm']}")
    print(f"Level: {task['level']}")
    print(f"Status: {task['status']}")
    print(f"Create Date: {task['create_dt']}")
    print()
    
    # Get details
    cursor.execute("SELECT * FROM tb_task_dtl WHERE task_id = ? ORDER BY step_seq ASC", (task['id'],))
    details = cursor.fetchall()
    for d in details:
        print(f"=== STEP {d['step_seq']}: {d['step_name']} ===")
        print(f"Status: {d['status']}")
        print(f"Next Step: {d['next_step']}")
        params = d['parameters']
        try:
            decoded = json.loads(params)
            print(json.dumps(decoded, indent=2, ensure_ascii=False))
        except:
            print(params)
        print()

conn.close()
