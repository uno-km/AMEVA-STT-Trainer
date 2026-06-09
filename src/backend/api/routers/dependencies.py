import os
from typing import Optional
from fastapi import Header, HTTPException

# 향후 환경 변수 AMEVA_API_KEY 설정 시, X-API-Key 헤더로 인증 수행
AMEVA_API_KEY = os.environ.get("AMEVA_API_KEY", "")

def verify_api_key(x_api_key: Optional[str] = Header(None)):
    if AMEVA_API_KEY and x_api_key != AMEVA_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return True
