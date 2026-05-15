import psutil
import socket
import os
from src.backend.core.pseudo_router import router

class HardwareManager:
    def __init__(self):
        # 실제 물리 코어가 아닌 논리 스레드 수 파악
        self.total_cores = psutil.cpu_count(logical=True)
        self.process = psutil.Process(os.getpid())
        
        # 현재 프로세스에 할당된 코어 수 (초기엔 전체로 가정)
        try:
            self.allocated_cores = len(self.process.cpu_affinity())
        except AttributeError:
            # CPU affinity를 지원하지 않는 OS의 경우 fallback
            self.allocated_cores = self.total_cores

    def check_internet(self) -> bool:
        """인터넷 연결 상태 확인 (8.8.8.8 및 1.1.1.1 시도)"""
        for target in ["8.8.8.8", "1.1.1.1"]:
            try:
                socket.setdefaulttimeout(1)
                socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((target, 53))
                return True
            except socket.error:
                continue
        return False

    def get_system_status(self) -> dict:
        """현재 시스템의 실시간 상태를 반환합니다."""
        try:
            current_affinity = len(self.process.cpu_affinity())
            self.allocated_cores = current_affinity
        except AttributeError:
            pass
            
        return {
            "total_cores": self.total_cores,
            "allocated_cores": self.allocated_cores,
            "cpu_percent": psutil.cpu_percent(interval=None),
            "process_cpu_percent": self.process.cpu_percent(interval=None),
            "memory_usage_mb": self.process.memory_info().rss / (1024 * 1024),
            "internet_connected": self.check_internet()
        }

    def set_cpu_affinity(self, target_cores: int) -> dict:
        """프로세스가 사용할 수 있는 CPU 코어 수를 동적으로 제한/확장합니다."""
        if target_cores < 1:
            target_cores = 1
        elif target_cores > self.total_cores:
            target_cores = self.total_cores
            
        try:
            # 0번 코어부터 target_cores 개수만큼 할당 (0, 1, 2... target_cores-1)
            affinity_list = list(range(target_cores))
            self.process.cpu_affinity(affinity_list)
            self.allocated_cores = target_cores
            return {"success": True, "allocated": target_cores, "affinity": affinity_list}
        except Exception as e:
            return {"success": False, "error": str(e)}

hw_manager = HardwareManager()

# --- API Endpoints ---

@router.get("/api/v1/hardware/status")
def get_hardware_status():
    return hw_manager.get_system_status()

@router.post("/api/v1/hardware/affinity")
def update_affinity(body: dict):
    cores = body.get("cores", hw_manager.total_cores)
    return hw_manager.set_cpu_affinity(cores)
