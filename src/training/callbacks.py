"""
src/training/callbacks.py
Rich 대시보드 연동 학습 콜백.
"""
from transformers import TrainerCallback, TrainingArguments, TrainerState, TrainerControl
from src.utils import logger

# TrainerCallback 을 상속받아 학습 이벤트를 가로채는 커스텀 콜백 클래스
class DashboardCallback(TrainerCallback):
    def on_step_end(self, args: TrainingArguments, state: TrainerState, control: TrainerControl, **kwargs):
        """매 학습 스텝이 끝날 때마다 호출되어 대시보드 진행률을 갱신합니다."""
        if state.max_steps > 0:
            pct = (state.global_step / state.max_steps) * 100
            logger.update_progress(pct)
            
            # 대시보드 상단 상태 메시지 실시간 갱신 (1스텝 단위)
            # 로그(on_log)가 찍히기 전이라도 현재 스텝 번호를 보여줌
            logger.set_status(sub_task=f"Step: {state.global_step}/{state.max_steps} ({pct:.1f}%)")

    def on_log(self, args, state, control, logs=None, **kwargs):
        # logs 딕셔너리가 없으면 처리할 정보가 없으므로 즉시 반환
        if logs is None: return
        
        # 현재까지 진행된 학습 스텝 번호
        step = state.global_step
        # 해당 스텝의 학습 손실값 (없으면 "N/A" 문자열로 대체)
        loss = logs.get("loss", "N/A")
        
        if isinstance(loss, (float, int)):
            # Loss 값이 있을 경우 대시보드 메인 상태에 표시
            status_msg = f"Step: {step} | Loss: {loss:.4f}"
            logger.set_status("Whisper Fine-tuning", status_msg)
            # 로그 파일에도 기록
            logger.info(f"Step {step:5d}: Loss={loss:.6f}")

    def on_epoch_end(self, args, state, control, **kwargs):
        # 매 에폭 종료 시 완료 메시지를 성공 로그로 출력
        logger.success(f"Epoch {state.epoch:.1f} 완료")
