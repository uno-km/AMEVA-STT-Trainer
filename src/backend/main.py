import sys
import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 시스템 경로에 프로젝트 루트 추가
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.backend.api.pipeline_api import router as pipeline_router

app = FastAPI(
    title="AMEVA-STT-Trainer Headless API",
    description="엔터프라이즈 MLOps 파이프라인 제어를 위한 REST API 서버",
    version="1.0.0"
)

# CORS 설정 (외부 호출 개방)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipeline_router)

@app.get("/")
def root():
    return {"message": "AMEVA-STT-Trainer API is running. Visit /docs for Swagger UI."}

if __name__ == "__main__":
    uvicorn.run("src.backend.main:app", host="0.0.0.0", port=8000, reload=False)
