import sqlite3
from typing import List, Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.backend.core.database import db_manager
from src.backend.api.routers.dependencies import verify_api_key

router = APIRouter(prefix="/api/v1/db", tags=["Database"])

class SqlQueryRequest(BaseModel):
    sql: str
    params: List[Any] = []

@router.post("/query", dependencies=[Depends(verify_api_key)])
def run_db_query(req: SqlQueryRequest):
    if not req.sql.strip().lower().startswith("select") and not req.sql.strip().lower().startswith("pragma"):
        return {"error": "Only SELECT or PRAGMA queries are allowed."}
    try:
        with db_manager.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(req.sql, req.params)
            rows = cur.fetchall()
            if not rows: return {"columns": [], "rows": []}
            cols = list(rows[0].keys())
            return {"columns": cols, "rows": [list(r) for r in rows]}
    except Exception as e:
        return {"error": str(e)}
