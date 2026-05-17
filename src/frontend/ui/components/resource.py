from src.frontend.ui.core.qt import *

class ResourcePanel(QFrame):
    """
    AMEVA Premium Resource Monitor (Slim CPU & Core Allocation Edition)
    - Displays real-time CPU Usage.
    - Provides a real-time slider to dynamically allocate/restrict CPU cores.
    - RAM & GPU are removed to prevent redundancy and fix the broken 0.1% indicator.
    """
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.setFixedHeight(60) # 60px로 여유롭게 설정
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {ctx.get_color('bg_panel')};
                border: 1px solid {ctx.get_color('border')};
                border-radius: 8px;
            }}
            QLabel {{ 
                color: {ctx.get_color('text')}; 
                font-size: 10px; 
                font-weight: bold; 
                border: none;
                background: transparent;
            }}
            QProgressBar {{
                background-color: {ctx.get_color('bg_dark')};
                border: none;
                border-radius: 2px;
                height: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {ctx.get_color('accent')};
                border-radius: 2px;
            }}
            QSlider::groove:horizontal {{
                border: none;
                height: 4px;
                background: {ctx.get_color('bg_dark')};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {ctx.get_color('accent')};
                border: none;
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(20)
        
        # --- Left Column: CPU Usage ---
        cpu_widget = QWidget()
        cpu_widget.setStyleSheet("background: transparent; border: none;")
        cpu_layout = QVBoxLayout(cpu_widget)
        cpu_layout.setContentsMargins(0, 0, 0, 0)
        cpu_layout.setSpacing(4)
        
        self.cpu_lbl = QLabel("CPU: 0%")
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setTextVisible(False)
        self.cpu_bar.setFixedHeight(4)
        
        cpu_layout.addWidget(self.cpu_lbl)
        cpu_layout.addWidget(self.cpu_bar)
        layout.addWidget(cpu_widget, 1) # 비율 1
        
        # --- Right Column: CPU Core Allocation Slider ---
        # 앱 기동 시 백엔드에서 사용자 사양에 맞는 코어 정보 최초 조회
        try:
            hw = ctx.api.get("/api/v1/hardware/status")
            self.total_cores = hw.get("total_cores", 8) if hw else 8
            self.allocated_cores = hw.get("allocated_cores", self.total_cores) if hw else self.total_cores
        except Exception:
            self.total_cores = 8
            self.allocated_cores = 8
            
        affinity_widget = QWidget()
        affinity_widget.setStyleSheet("background: transparent; border: none;")
        aff_layout = QVBoxLayout(affinity_widget)
        aff_layout.setContentsMargins(0, 0, 0, 0)
        aff_layout.setSpacing(4)
        
        self.aff_lbl = QLabel(f"Cores: {self.allocated_cores}/{self.total_cores}")
        self.aff_slider = QSlider(Qt.Orientation.Horizontal)
        self.aff_slider.setMinimum(1)
        self.aff_slider.setMaximum(self.total_cores)
        self.aff_slider.setValue(self.allocated_cores)
        self.aff_slider.setFixedHeight(12)
        
        # 슬라이더 값 변경 시 실시간 코어 할당 바인딩
        self.aff_slider.valueChanged.connect(self.on_slider_changed)
        
        aff_layout.addWidget(self.aff_lbl)
        aff_layout.addWidget(self.aff_slider)
        layout.addWidget(affinity_widget, 1) # 비율 1
        
    def on_slider_changed(self, val):
        """슬라이더 조정 즉시 실시간으로 코어 배분 API 전송"""
        self.aff_lbl.setText(f"Cores: {val}/{self.total_cores}")
        
        # 메인 윈도우 및 프리젠터에서 현재 활성화된 태스크 ID 역추적
        task_id = None
        parent = self.parentWidget()
        while parent is not None:
            if hasattr(parent, 'presenter'):
                task_id = parent.presenter.active_log_task_id
                break
            parent = parent.parentWidget()
            
        try:
            payload = {"cores": val}
            if task_id:
                payload["task_id"] = task_id
            self.ctx.api.post("/api/v1/hardware/affinity", payload)
        except Exception as e:
            print(f"[Affinity Bind Error] {e}")
            
    def update_stats(self, res):
        """실시간 폴링 데이터로 CPU 사용율 갱신"""
        cpu = res.get("cpu", 0)
        self.cpu_lbl.setText(f"CPU: {cpu:.1f}%")
        self.cpu_bar.setValue(int(cpu))
        
        # 슬라이더를 직접 사용자가 조절하고 있지 않을 때만, 실시간 할당값 동기화
        if not self.aff_slider.isSliderDown():
            try:
                allocated = res.get("allocated_cores")
                if allocated is not None:
                    self.aff_slider.setValue(allocated)
                    self.aff_lbl.setText(f"Cores: {allocated}/{self.total_cores}")
            except Exception:
                pass
