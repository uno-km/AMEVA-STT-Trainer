import os, sys
sys.path.insert(0, '.')
from src.backend.core.database import db_manager

outputs_dir = 'outputs'
for task_id in os.listdir(outputs_dir):
    lora_dir = os.path.join(outputs_dir, task_id, 'lora_adapter')
    if os.path.isdir(lora_dir):
        ckpts = [d for d in os.listdir(lora_dir) if d.startswith('checkpoint-')]
        for ckpt_name in sorted(ckpts, key=lambda x: int(x.split('-')[-1])):
            ckpt_path = os.path.abspath(os.path.join(lora_dir, ckpt_name))
            if os.path.isdir(ckpt_path):
                db_manager.insert_checkpoint(task_id, ckpt_path, ckpt_name, step_level=2)
                print(f"Backfilled: {task_id[:8]} -> {ckpt_name}")

for tid in os.listdir(outputs_dir):
    latest = db_manager.get_latest_checkpoint(tid, 2)
    if latest:
        print(f"Latest for {tid[:8]}: {latest['ckpt_name']} at {latest['ckpt_path']}")
