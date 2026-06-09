import os
import psutil
from fastapi import APIRouter, Depends

from src.backend.api.routers.dependencies import verify_api_key

router = APIRouter(prefix="/api/v1/system", tags=["System"])

@router.get("/resources", dependencies=[Depends(verify_api_key)])
def get_resources():
    try:
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().percent
        ram_used = psutil.virtual_memory().used / (1024 ** 3)
        ram_total = psutil.virtual_memory().total / (1024 ** 3)
        gpu = 0
        gpu_mem = "N/A"
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            if gpus: 
                gpu = gpus[0].load * 100
                gpu_mem = f"{gpus[0].memoryUsed:.0f}/{gpus[0].memoryTotal:.0f} MB"
        except: pass
        
        # Windows 환경 대응: 프로젝트 루트 기준으로 디스크 체크
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
        disk = psutil.disk_usage(project_root)
        disk_pct = disk.percent
        disk_used = disk.used / (1024**3)
        disk_total = disk.total / (1024**3)
        
        procs = []
        for p in sorted([p.info for p in psutil.process_iter(['pid','name','cpu_percent','memory_info'])], key=lambda p: p.get('cpu_percent') or 0, reverse=True)[:5]:
            mem_mb = (p.get('memory_info').rss / (1024**2)) if p.get('memory_info') else 0
            procs.append({
                "pid": p.get('pid', ''),
                "name": p.get('name', '')[:25],
                "cpu": f"{p.get('cpu_percent', 0):.1f}",
                "mem": f"{mem_mb:.1f} MB"
            })
            
        return {
            "cpu": cpu, "ram": ram, "gpu": gpu, "gpu_mem": gpu_mem,
            "ram_used": ram_used, "ram_total": ram_total,
            "disk_pct": disk_pct, "disk_used": disk_used, "disk_total": disk_total,
            "processes": procs
        }
    except Exception as e:
        return {"error": str(e), "cpu": 0, "ram": 0, "gpu": 0}
