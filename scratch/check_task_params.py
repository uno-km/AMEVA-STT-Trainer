import sqlite3
import json

conn = sqlite3.connect("db/stt_trainer.db")
cursor = conn.cursor()
cursor.execute("SELECT * FROM tb_task WHERE id = 'a28cf223-f1c6-4c5e-914a-8f828bfe721f'")
task = cursor.fetchone()
print("Task Row:", task)

cursor.execute("SELECT * FROM tb_task_dtl WHERE task_id = 'a28cf223-f1c6-4c5e-914a-8f828bfe721f'")
details = cursor.fetchall()
for d in details:
    print("Dtl Row:", d)
    if d[4]: # parameters is at index 4 (dtl_id, task_id, step_seq, step_name, parameters, next_step, status, ...)
        try:
            print("  Decoded Params:", json.loads(d[4]))
        except Exception as e:
            print("  Error decoding:", e)

conn.close()
