import os
import requests
import json
from src.utils import logger

class WebhookManager:
    def __init__(self):
        # 환경 변수나 설정에서 Webhook URL을 가져옴 (향후 Telegram 서버 등)
        self.webhook_url = os.environ.get("AMEVA_WEBHOOK_URL", "")
    
    def send_notification(self, task_id: str, level: int, status: str, message: str):
        if not self.webhook_url:
            return
            
        payload = {
            "task_id": task_id,
            "level": level,
            "status": status,
            "message": message,
            "project": "AMEVA-STT-Trainer"
        }
        
        try:
            # 타임아웃을 짧게 주어 메인 스레드 블로킹 방지 (혹은 비동기/백그라운드로 쏠 수 있음)
            response = requests.post(self.webhook_url, json=payload, timeout=3.0)
            response.raise_for_status()
            logger.info(f"Webhook 발송 성공: {self.webhook_url} [{status}]")
        except Exception as e:
            logger.error(f"Webhook 발송 실패: {e}")

webhook_manager = WebhookManager()
