import sys
import os

# 현재 파일 위치(src/frontend/client/api_client.py) 기준 3단계 상위 폴더를 루트로 동적 계산
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import the local router directly. 
# In a real web app, this would use requests.get() or similar.
from src.backend.core.pseudo_router import router

# Ensure the backend modules are loaded so they register their routes
import src.backend.hardware.resource_manager
import src.backend.api.pipeline_api

class APIClient:
    """
    프론트엔드용 API 클라이언트.
    REST API 구조를 시뮬레이션하여 백엔드 라우터로 요청을 보냅니다.
    """
    @staticmethod
    def get(path: str) -> dict:
        response = router.request("GET", path)
        if response.get("status") == 200:
            return response.get("data", {})
        else:
            print(f"[API Client Error] GET {path}: {response}")
            return {}

    @staticmethod
    def post(path: str, body: dict = None) -> dict:
        response = router.request("POST", path, body)
        if response.get("status") == 200:
            return response.get("data", {})
        else:
            print(f"[API Client Error] POST {path}: {response}")
            return {}

api_client = APIClient()
