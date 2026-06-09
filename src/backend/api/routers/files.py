import os
import csv
from typing import Optional
from fastapi import APIRouter, Depends

from src.backend.api.routers.dependencies import verify_api_key

router = APIRouter(prefix="/api/v1/files", tags=["Files"])

def scan_directory(base_path):
    if not os.path.exists(base_path):
        return []
    
    def get_recursive_items(path, depth=0):
        if depth > 10: return []
        items = []
        try:
            for entry in os.scandir(path):
                if entry.name == "chunks" and entry.is_dir():
                    items.append({
                        "name": entry.name, "is_dir": True, "path": entry.path, "size": 0, "children": []
                    })
                    continue
                item = {
                    "name": entry.name, "is_dir": entry.is_dir(), "path": entry.path, "size": entry.stat().st_size if entry.is_file() else 0
                }
                if entry.is_dir():
                    item["children"] = get_recursive_items(entry.path, depth + 1)
                items.append(item)
        except Exception:
            pass
        return items
    return get_recursive_items(base_path)

@router.get("/explorer", dependencies=[Depends(verify_api_key)])
def get_files_explorer():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    return {
        "dataset": scan_directory(os.path.join(base_dir, "dataset")),
        "logs": scan_directory(os.path.join(base_dir, "logs")),
        "outputs": scan_directory(os.path.join(base_dir, "outputs")),
        "configs": scan_directory(os.path.join(base_dir, "configs"))
    }

@router.get("/read", dependencies=[Depends(verify_api_key)])
def read_file_content(path: str):
    if not os.path.exists(path):
        return {"error": "File not found"}
    try:
        if path.endswith(".csv"):
            with open(path, newline='', encoding='utf-8', errors='replace') as f:
                return {"type": "csv", "content": list(csv.reader(f))}
        else:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return {"type": "text", "content": f.readlines()}
    except Exception as e:
        return {"error": str(e)}

@router.get("/search", dependencies=[Depends(verify_api_key)])
def search_files(keyword: str, exts: Optional[str] = None):
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    search_dirs = [os.path.join(base_dir, d) for d in ("dataset","outputs","logs","configs","scripts") if os.path.isdir(os.path.join(base_dir, d))]
    
    ext_list = None
    if exts:
        ext_list = [e.strip() if e.strip().startswith(".") else f".{e.strip()}" for e in exts.split(",") if e.strip()]
        
    results = []
    skip = {"chunks", "__pycache__", ".git", "venv"}
    
    for d in search_dirs:
        for root, dirs, files in os.walk(d):
            dirs[:] = [dir_name for dir_name in dirs if dir_name not in skip]
            for f in files:
                if ext_list and os.path.splitext(f)[1].lower() not in ext_list:
                    continue
                if keyword.lower() in f.lower():
                    filepath = os.path.join(root, f)
                    try:
                        size = os.path.getsize(filepath)
                        results.append({"name": f, "path": filepath, "size": size, "dir": root})
                    except: pass
                    
    return {"results": results[:100]}
