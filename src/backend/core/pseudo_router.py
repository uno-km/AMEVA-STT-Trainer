import json
import traceback
from typing import Callable, Dict, Any, Tuple

class PseudoRouter:
    """
    프론트엔드 UI와 백엔드 비즈니스 로직을 완벽히 분리하기 위한 가상 REST API 라우터.
    실제 HTTP 서버를 띄우지 않고 메모리 상에서 API 요청/응답을 시뮬레이션합니다.
    추후 FastAPI 등으로 손쉽게 마이그레이션 가능하도록 설계되었습니다.
    """
    def __init__(self):
        self._routes: Dict[Tuple[str, str], Callable] = {}

    def get(self, path: str):
        def decorator(func: Callable):
            self._routes[(path, 'GET')] = func
            return func
        return decorator

    def post(self, path: str):
        def decorator(func: Callable):
            self._routes[(path, 'POST')] = func
            return func
        return decorator

    def request(self, method: str, path: str, body: dict = None) -> dict:
        """프론트엔드에서 호출하는 가상 HTTP Request 메서드"""
        # 쿼리 스트링 분리 (예: /api/v1/tasks/report?task_id=123)
        query_params = {}
        clean_path = path
        if "?" in path:
            clean_path, query_str = path.split("?", 1)
            for pair in query_str.split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    query_params[k] = v

        handler = self._routes.get((clean_path, method.upper()))
        if not handler:
            return {"status": 404, "error": f"Route not found: {method} {path}"}
        
        try:
            if method.upper() == 'POST':
                # POST는 body와 query_params를 함께 전달할 수 있음
                response = handler(body or {})
            else:
                # GET은 URL 파라미터들을 함수의 인자로 전달
                import inspect
                sig = inspect.signature(handler)
                if query_params and len(sig.parameters) > 0:
                    # 함수가 인자를 받는 경우만 전달
                    response = handler(**query_params)
                else:
                    response = handler()
                
            return {"status": 200, "data": response}
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"[Router Error] {error_trace}")
            return {"status": 500, "error": str(e), "trace": error_trace}

# 전역 싱글톤 라우터 인스턴스
router = PseudoRouter()
