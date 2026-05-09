"""
src/training/callbacks.py
Rich 대시보드 연동 학습 콜백.
"""
from transformers import TrainerCallback, TrainingArguments, TrainerState, TrainerControl
from src.utils import logger

# TrainerCallback 을 상속받아 학습 이벤트를 가로채는 커스텀 콜백 클래스
class DashboardCallback(TrainerCallback):
    def on_log(self, args, state, control, logs=None, **kwargs):
        # logs 딕셔너리가 없으면 처리할 정보가 없으므로 즉시 반환
        if logs is None: return
        # 현재까지 진행된 학습 스텝 번호
        step = state.global_step
        # 해당 스텝의 학습 손실값 (없으면 "N/A" 문자열로 대체)
        loss = logs.get("loss", "N/A")
        
        # loss가 실수형이면 소수점 4자리까지 포맷팅, 아니면 스텝 번호만 표시
        status_msg = f"Step: {step} | Loss: {loss:.4f}" if isinstance(loss, float) else f"Step: {step}"
        # 대시보드 상태 메시지 갱신
        logger.set_status("Whisper Fine-tuning 중", status_msg)
        
        # loss 값이 실수형일 때만 파일 로그에 상세 기록 (소수점 6자리)
        if isinstance(loss, float):
            logger.info(f"Step {step:5d}: Loss={loss:.6f}")

    def on_epoch_end(self, args, state, control, **kwargs):
        # 매 에폭 종료 시 완료 메시지를 성공 로그로 출력
        logger.success(f"Epoch {state.epoch:.1f} 완료")
