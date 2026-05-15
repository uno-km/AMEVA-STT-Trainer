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
            
            if chunk_count % 1000 == 0:
                print(f"Migrated {chunk_count} chunks...")
                
    db_manager.add_log("INFO", f"Successfully migrated {chunk_count} chunks to DB.", task_id)
    print(f"Migration complete! {chunk_count} chunks added under Task ID: {task_id}")

if __name__ == "__main__":
    migrate_legacy_data()
