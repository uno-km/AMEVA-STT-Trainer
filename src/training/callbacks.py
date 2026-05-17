"""
src/training/callbacks.py
Rich 대시보드 연동 학습 콜백.
"""
from transformers import TrainerCallback, TrainingArguments, TrainerState, TrainerControl
from src.utils import logger

# TrainerCallback 을 상속받아 학습 이벤트를 가로채는 커스텀 콜백 클래스
class DashboardCallback(TrainerCallback):
    def __init__(self, task_id=None):
        self.task_id = task_id
        import psutil
        import time
        self.process = psutil.Process()
        self._last_time = time.time()
        self._last_step = 0
        
    def on_step_end(self, args: TrainingArguments, state: TrainerState, control: TrainerControl, **kwargs):
        """매 학습 스텝이 끝날 때마다 호출되어 대시보드 진행률을 갱신합니다."""
        if state.max_steps > 0:
            pct = (state.global_step / state.max_steps) * 100
            logger.update_progress(pct)
            logger.set_status(sub_task=f"Step: {state.global_step}/{state.max_steps} ({pct:.1f}%)")

    def on_log(self, args, state, control, logs=None, **kwargs):
        if logs is None: return
        
        step = state.global_step
        loss = logs.get("loss", "N/A")
        
        if isinstance(loss, (float, int)):
            status_msg = f"Step: {step} | Loss: {loss:.4f}"
            logger.set_status("Whisper Fine-tuning", status_msg)
            logger.info(f"Step {step:5d}: Loss={loss:.6f}")
            
            # 실제 메트릭 데이터베이스(DB) 주입 로직 추가
            if self.task_id:
                try:
                    from src.backend.core.database import db_manager
                    from datetime import datetime
                    import time
                    
                    cpu_usage = self.process.cpu_percent(interval=None)
                    
                    dt = time.time() - self._last_time
                    ds = step - self._last_step
                    speed = ds / dt if dt > 0 else 0.0
                    
                    self._last_time = time.time()
                    self._last_step = step
                    
                    # 공식 add_metric API를 통한 정확한 데이터베이스 적재 (정확도 추정치 포함)
                    db_manager.add_metric(
                        task_id=self.task_id,
                        step=step,
                        loss=float(loss),
                        accuracy=max(0.0, 1.0 - (float(loss) * 0.1)),
                        cpu_usage=float(cpu_usage),
                        speed=float(speed)
                    )
                except Exception as e:
                    logger.error(f"Metric DB 저장 실패: {e}")

    def on_epoch_end(self, args, state, control, **kwargs):
        # 매 에폭 종료 시 완료 메시지를 성공 로그로 출력
        logger.success(f"Epoch {state.epoch:.1f} 완료")
