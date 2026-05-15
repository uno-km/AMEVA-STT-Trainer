import os
import sys
import csv

# Add project root to sys path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.backend.core.database import db_manager

def migrate_legacy_data():
    dataset_dir = os.path.join(project_root, "dataset")
    metadata_file = os.path.join(dataset_dir, "metadata.csv")
    
    if not os.path.exists(metadata_file):
        print("No legacy metadata.csv found.")
        return
        
    print("Migrating legacy data to new SQLite DB...")
    
    # 1. Create a legacy task
    task_id = db_manager.create_task("슈카월드_과거기록_Legacy")
    db_manager.add_log("INFO", "Legacy Data Migration Started", task_id)
    
    # 2. Create Metadata record
    meta_id = db_manager.create_metadata(task_id, "metadata.csv", dataset_dir)
    
    # 3. Parse CSV and create chunks
    chunk_count = 0
    with open(metadata_file, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            chunk_path = row.get("file_name", "")
            chunk_name = os.path.basename(chunk_path)
            script = row.get("transcription", "")
            db_manager.create_chunk(meta_id, chunk_name, chunk_path, script)
            chunk_count += 1
            
    # 4. Legacy Log Migration (logs/pipeline_run.log 읽기)
    log_file = os.path.join(project_root, "logs", "pipeline_run.log")
    log_count = 0
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                # [timestamp] [level] message 형식 파싱 시도
                try:
                    if "]" in line:
                        parts = line.split("]", 2)
                        level = parts[1].strip().replace("[", "")
                        message = parts[2].strip()
                        db_manager.add_log(level, message, task_id)
                        log_count += 1
                except:
                    continue
                    
    db_manager.update_task_status(task_id, 3, "SUCCESS", f"Legacy migration complete. {chunk_count} chunks, {log_count} logs added.")
    print(f"Migration complete! Chunks: {chunk_count}, Logs: {log_count}")

if __name__ == "__main__":
    migrate_legacy_data()
