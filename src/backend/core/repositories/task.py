import uuid
from datetime import datetime
from .base import BaseRepository

class TaskRepository(BaseRepository):
    """
    [TaskRepository] tb_task 및 tb_task_dtl(워크플로우 디테일)에 특화된 데이터 모델 레이어
    """
    def create(self, tsk_nm: str) -> str:
        """새로운 STT 학습 태스크 레코드를 생성하고 UUID ID를 반환합니다."""
        task_id = str(uuid.uuid4())
        create_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.get_connection() as conn:
            conn.execute(
                'INSERT INTO tb_task (id, tsk_nm, create_dt, level, status) VALUES (?, ?, ?, 1, "RUNNING")', 
                (task_id, tsk_nm, create_dt)
            )
            conn.commit()
        return task_id

    def create_next_version(self, base_task_id: str) -> str:
        """기존 태스크 명칭의 시퀀셜 버전(예: 1_Task -> 2_Task)을 계산하여 다음 버전 태스크를 기동합니다."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT tsk_nm FROM tb_task WHERE id = ?', (base_task_id,))
            row = cursor.fetchone()
            if not row: 
                return self.create("Unknown_Task")
            old_name = row['tsk_nm']
            if "_" in old_name and old_name.split("_")[0].isdigit():
                version = int(old_name.split("_")[0]) + 1
                new_name = f"{version}_{'_'.join(old_name.split('_')[1:])}"
            else:
                new_name = f"2_{old_name}"
            return self.create(new_name)

    def update_status(self, task_id: str, level: int, status: str, log_msg: str = None, 
                      model_path: str = None, report_path: str = None, 
                      checkpoint_path: str = None, pipeline_config: str = None):
        """태스크의 공정 단계(Level), 성공/실패 여부(Status) 및 부가 산출물 경로를 업데이트하고 로그를 병합 적재합니다."""
        stts_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # [중단 감지 및 상태 정교화] 사용자가 중단 버튼을 누른 경우 status를 'CANCELED'로 격상!
        if log_msg and ("사용자에 의해 강제 종료" in log_msg or "중단되었습니다" in log_msg):
            status = "CANCELED"
            
        log_id = None
        if log_msg:
            # logs 레포지토리 또는 Facade 위임 호출로 무결성 연결
            log_id = self.db.logs.add(
                "INFO" if status == "SUCCESS" else "WARNING" if status == "CANCELED" else "ERROR" if status == "FAILED" else "INFO", 
                log_msg, 
                task_id
            )
            
        with self.get_connection() as conn:
            # 1. tb_task 마스터 테이블 상태 업데이트
            sql = "UPDATE tb_task SET level = ?, status = ?, stts_dt = ?"
            params = [level, status, stts_dt]
            if log_id:
                sql += ", log_id = ?"
                params.append(log_id)
            if model_path:
                sql += ", model_path = ?"
                params.append(model_path)
            if report_path:
                sql += ", report_path = ?"
                params.append(report_path)
            if checkpoint_path:
                sql += ", checkpoint_path = ?"
                params.append(checkpoint_path)
            if pipeline_config:
                sql += ", pipeline_config = ?"
                params.append(pipeline_config)
            sql += " WHERE id = ?"
            params.append(task_id)
            conn.cursor().execute(sql, params)
            
            # 2. tb_task_dtl 하위 단계의 개별 status 도 완벽하게 동기화!
            conn.cursor().execute(
                "UPDATE tb_task_dtl SET status = ? WHERE task_id = ? AND step_seq = ?",
                (status, task_id, level)
            )
            
            # 3. [자가 치유 - Self-healing] 2단계나 3단계 도중 취소/실패했다면, 이전 공정(1단계 혹은 2단계)은
            # 이미 완벽하게 완료된 것이 확실하므로 SUCCESS 상태로 자동 보정 보존해 줍니다!
            if status in ["FAILED", "CANCELED"] and level > 1:
                for prev_level in range(1, level):
                    conn.cursor().execute(
                        "UPDATE tb_task_dtl SET status = 'SUCCESS' WHERE task_id = ? AND step_seq = ?",
                        (task_id, prev_level)
                    )
            
            conn.commit()

    def add_detail(self, task_id: str, step_seq: int, step_name: str, parameters: str, next_step: int = None) -> int:
        """특정 태스크의 SOP 하위 단계(1~3단계) 실행 정보 및 JSON 파라미터 설정을 적재하거나 갱신합니다."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT dtl_id FROM tb_task_dtl WHERE task_id=? AND step_seq=?', (task_id, step_seq))
            row = cursor.fetchone()
            if row:
                cursor.execute('''
                    UPDATE tb_task_dtl 
                    SET step_name=?, parameters=?, next_step=?, status='PENDING'
                    WHERE dtl_id=?
                ''', (step_name, parameters, next_step, row['dtl_id']))
                dtl_id = row['dtl_id']
            else:
                cursor.execute('''
                    INSERT INTO tb_task_dtl (task_id, step_seq, step_name, parameters, next_step) 
                    VALUES (?, ?, ?, ?, ?)
                ''', (task_id, step_seq, step_name, parameters, next_step))
                dtl_id = cursor.lastrowid
            conn.commit()
            return dtl_id

    def get_all(self):
        """과거 모든 학습 이력을 생성일 최신순으로 일괄 로드합니다."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM tb_task ORDER BY create_dt DESC')
            return [dict(row) for row in cursor.fetchall()]

    def get_details(self, task_id: str):
        """특정 태스크에 결합된 상세 체이닝 정보 및 오디오 메타데이터/청크 관계망을 역정렬 취합하여 맵으로 반환합니다."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM tb_task WHERE id = ?', (task_id,))
            task = cursor.fetchone()
            if not task: 
                return None
            task_dict = dict(task)
            
            # 1. 상세 워크플로우 결합
            cursor.execute('SELECT * FROM tb_task_dtl WHERE task_id = ? ORDER BY step_seq ASC', (task_id,))
            task_dict['details'] = [dict(row) for row in cursor.fetchall()]
            
            # 2. 오디오 메타데이터 및 조각(Chunks) 계층 일괄 취합
            cursor.execute('SELECT * FROM tb_metadata WHERE task_id = ?', (task_id,))
            metadatas = [dict(row) for row in cursor.fetchall()]
            for meta in metadatas:
                cursor.execute('SELECT * FROM tb_chunk WHERE meta_id = ?', (meta['meta_id'],))
                meta['chunks'] = [dict(row) for row in cursor.fetchall()]
            task_dict['metadatas'] = metadatas
            return task_dict
