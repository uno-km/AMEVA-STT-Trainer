from src.frontend.ui.core.qt import *
from PyQt6.QtCore import Qt, QPointF, pyqtSignal, QRect
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient, QPainterPath, QFont
from PyQt6.QtWidgets import QWidget, QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QScrollBar
from datetime import datetime

class SimpleChart(QWidget):
    """QPainter를 이용한 핀테크/증권사 앱 스타일의 프리미엄 실시간 시계열 차트 위젯"""
    scroll_changed = pyqtSignal(int)
    
    def __init__(self, color="#a6e3a1"):
        super().__init__()
        self.data = []  # List of {"value": float, "time": str}
        self.max_points = 50
        self.line_color = QColor(color)
        self.scroll_offset = 0  # 과거 데이터 조회를 위한 오프셋
        
        # Y축 틱 및 범위 제어 프로퍼티 (기본값은 동적 오토 스케일링)
        self.y_min = None
        self.y_max = None
        self.y_suffix = ""
        
        # 인터랙션 변수 설정
        self.setMouseTracking(True)
        self.hovered_idx = None
        
        # 초기 구동 시점부터 차트가 빈 화면이 아닌 과거 baseline이 차있는 상태로 보이도록 사전 패딩 처리
        self.prefill_data(0.0)
        
    def prefill_data(self, default_value=0.0):
        from datetime import datetime, timedelta
        now = datetime.now()
        self.data = []
        for i in range(self.max_points):
            t = now - timedelta(seconds=(self.max_points - i) * 0.5)
            self.data.append({
                "value": default_value,
                "time": t.strftime("%H:%M:%S")
            })
        self.update()
        
    def add_data(self, value):
        current_time = datetime.now().strftime("%H:%M:%S")
        if isinstance(value, dict):
            self.data.append(value)
        else:
            self.data.append({"value": float(value), "time": current_time})
        self.update()

    def wheelEvent(self, event):
        """마우스 휠로 과거 데이터 스크롤"""
        delta = event.angleDelta().y()
        if delta > 0:
            self.scroll_offset = min(self.scroll_offset + 5, max(0, len(self.data) - self.max_points))
        else:
            self.scroll_offset = max(self.scroll_offset - 5, 0)
        self.scroll_changed.emit(self.scroll_offset)
        self.update()

    def mouseMoveEvent(self, event):
        """마우스 위치 기반 가장 가까운 시계열 데이터 포인트 탐색 (크로스헤어 바인딩)"""
        if not self.data:
            return
            
        w, h = self.width(), self.height()
        
        # 여백 값 정의
        left_margin = 60
        right_margin = 15
        chart_w = w - left_margin - right_margin
        
        # 현재 화면에 그려지는 윈도우 슬라이스 계산
        start_idx = max(0, len(self.data) - self.max_points - self.scroll_offset)
        end_idx = start_idx + self.max_points
        view_data = self.data[start_idx:end_idx]
        
        if not view_data:
            return
            
        # 마우스 X 좌표 추출
        try:
            mx = event.position().x()
        except AttributeError:
            mx = event.x()
            
        # 차트 가용 가로폭 내에서 마우스 컬리전 영역 매핑
        mx_adjusted = mx - left_margin
        point_spacing = chart_w / (len(view_data) - 1) if len(view_data) > 1 else chart_w
        
        if point_spacing > 0:
            local_idx = round(mx_adjusted / point_spacing)
            local_idx = max(0, min(len(view_data) - 1, local_idx))
            self.hovered_idx = start_idx + local_idx
        else:
            self.hovered_idx = start_idx
            
        self.update()

    def leaveEvent(self, event):
        """마우스 이탈 시 크로스헤어 및 툴팁 즉각 삭제"""
        self.hovered_idx = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        
        # 차트 내부 정밀 여백 정의 (Y축 수치 표기를 위한 레이아웃 공간 확보)
        left_margin = 60
        right_margin = 15
        top_margin = 20
        bottom_margin = 25
        
        chart_w = w - left_margin - right_margin
        chart_h = h - top_margin - bottom_margin
        
        if not self.data:
            # 데이터 없음 플레이스홀더 출력
            painter.setPen(QPen(QColor("#6c7086")))
            painter.setFont(QFont("Malgun Gothic", 10))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "수집 중인 데이터가 없습니다...")
            return
            
        # 1. 현재 뷰 데이터 윈도우 계산
        start_idx = max(0, len(self.data) - self.max_points - self.scroll_offset)
        end_idx = start_idx + self.max_points
        view_data = self.data[start_idx:end_idx]
        
        if not view_data:
            return
            
        raw_vals = [d["value"] for d in view_data]
        max_val = max(raw_vals)
        min_val = min(raw_vals)
        
        # Y축 도메인 결정 (고정 범위 사용 혹은 오토 스케일링)
        if self.y_min is not None and self.y_max is not None:
            domain_min = self.y_min
            domain_max = self.y_max
        else:
            val_range = max_val - min_val if max_val > min_val else 1.0
            domain_max = max_val + (val_range * 0.12)
            domain_min = min_val - (val_range * 0.12)
            
        domain_range = domain_max - domain_min if domain_max > domain_min else 1.0
        
        # 2. 배경 격자선 및 Y축 눈금선 (Grid & Tick System) 그리기
        grid_pen = QPen(QColor("#1e1e2e"), 1, Qt.PenStyle.SolidLine)
        painter.setPen(grid_pen)
        painter.setFont(QFont("Malgun Gothic", 8))
        
        # 가로 격자 및 Y축 정밀 눈금 수치 5개 분할 드로잉
        for i in range(5):
            y = int(top_margin + chart_h - (i * chart_h / 4))
            
            # 격자선 그리기 (차트 드로잉 영역 내부만)
            painter.drawLine(left_margin, y, w - right_margin, y)
            
            # 눈금 수치 텍스트 계산 및 포맷팅
            tick_val = domain_min + i * (domain_max - domain_min) / 4
            if self.y_suffix == "%":
                tick_text = f"{int(tick_val)}{self.y_suffix}"
            else:
                tick_text = f"{tick_val:.2f}{self.y_suffix}"
                
            # Y축 눈금 텍스트 인쇄
            painter.setPen(QPen(QColor("#6c7086")))
            rect = QRect(0, y - 8, left_margin - 8, 16)
            painter.drawText(rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, tick_text)
            painter.setPen(grid_pen)
            
        # 세로 격자선 (5개 분할)
        for i in range(5):
            x = int(left_margin + i * (chart_w / 4))
            painter.drawLine(x, top_margin, x, top_margin + chart_h)
            
        # 3. 데이터 좌표 계산
        points = []
        point_spacing = chart_w / (len(view_data) - 1) if len(view_data) > 1 else chart_w
        
        for i, item in enumerate(view_data):
            x = left_margin + i * point_spacing
            norm_y = (item["value"] - domain_min) / domain_range
            # 차트 상하 영역 클램핑 가드
            norm_y = max(0.0, min(1.0, norm_y))
            y = top_margin + chart_h - (norm_y * chart_h)
            points.append(QPointF(x, y))
            
        # 4. 하단 그라디언트 채우기 (Area Gradient Fill)
        gradient_path = QPainterPath()
        gradient_path.moveTo(left_margin, top_margin + chart_h)
        gradient_path.lineTo(points[0].x(), points[0].y())
        for pt in points:
            gradient_path.lineTo(pt.x(), pt.y())
        gradient_path.lineTo(points[-1].x(), top_margin + chart_h)
        gradient_path.closeSubpath()
        
        area_gradient = QLinearGradient(0, top_margin, 0, top_margin + chart_h)
        area_gradient.setColorAt(0.0, QColor(self.line_color.red(), self.line_color.green(), self.line_color.blue(), 55))
        area_gradient.setColorAt(1.0, QColor(self.line_color.red(), self.line_color.green(), self.line_color.blue(), 0))
        painter.fillPath(gradient_path, QBrush(area_gradient))
        
        # 5. 메인 추세선 그리기
        line_path = QPainterPath()
        line_path.moveTo(points[0])
        for pt in points:
            line_path.lineTo(pt)
            
        painter.setPen(QPen(self.line_color, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(line_path)
        
        # 6. 하단 X축 시계열 라벨 (시작점, 중간점, 끝점 3개 출력)
        painter.setPen(QPen(QColor("#6c7086")))
        painter.setFont(QFont("Malgun Gothic", 8))
        if len(view_data) >= 2:
            # 시작점
            painter.drawText(left_margin, h - 8, view_data[0]["time"])
            # 중간점
            painter.drawText(int(left_margin + chart_w / 2) - 25, h - 8, view_data[int(len(view_data)/2)]["time"])
            # 끝점
            painter.drawText(w - right_margin - 50, h - 8, view_data[-1]["time"])
            
        # 7. 인터랙션 호버 이펙트 (크로스헤어 조준선 + 발광 노드 + 팝업 툴팁)
        if self.hovered_idx is not None and start_idx <= self.hovered_idx < end_idx:
            local_idx = self.hovered_idx - start_idx
            pt = points[local_idx]
            item = view_data[local_idx]
            
            # (1) 세로/가로 크로스헤어 조준선 (차트 드로잉 박스 내부로만 바운딩 제한)
            crosshair_pen = QPen(QColor("#45475a"), 1, Qt.PenStyle.DashLine)
            painter.setPen(crosshair_pen)
            painter.drawLine(int(pt.x()), top_margin, int(pt.x()), top_margin + chart_h)
            painter.drawLine(left_margin, int(pt.y()), w - right_margin, int(pt.y()))
            
            # (2) 발광 노드 이펙트
            # 외곽 링
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(self.line_color.red(), self.line_color.green(), self.line_color.blue(), 90)))
            painter.drawEllipse(pt, 9, 9)
            # 코어 서클
            painter.setBrush(QBrush(self.line_color))
            painter.drawEllipse(pt, 4.5, 4.5)
            
            # (3) 증권사 스타일 프리미엄 플로팅 툴팁 그리기
            tooltip_w, tooltip_h = 135, 52
            
            # 마우스 주변 플로팅 좌표 계산 (차트 경계선 오버 방지 자가치유 가드)
            tx = pt.x() + 15
            if tx + tooltip_w > w:
                tx = pt.x() - tooltip_w - 15
            ty = pt.y() - tooltip_h - 15
            if ty < 10:
                ty = pt.y() + 15
                
            # 툴팁 백그라운드 (유려한 블랙 박스 & 네온 테두리)
            painter.setPen(QPen(QColor("#313244"), 1))
            painter.setBrush(QBrush(QColor("#11111b")))
            painter.drawRoundedRect(int(tx), int(ty), tooltip_w, tooltip_h, 6, 6)
            
            # 툴팁 텍스트 드로잉
            # 시간 라벨
            painter.setPen(QPen(QColor("#cdd6f4")))
            painter.setFont(QFont("Malgun Gothic", 9, QFont.Weight.Bold))
            painter.drawText(int(tx) + 10, int(ty) + 20, f"⏳ {item['time']}")
            
            # 수치 라벨
            painter.setPen(QPen(self.line_color))
            painter.setFont(QFont("Malgun Gothic", 9, QFont.Weight.Bold))
            val_format = f"{item['value']:.2f}{self.y_suffix}" if self.y_suffix == "%" else f"{item['value']:.5f}"
            painter.drawText(int(tx) + 10, int(ty) + 40, f"📈 {val_format}")

class ChartWidget(QFrame):
    """제목, 최대화 버튼, 차트, 그리고 드래그 가능한 과거 이력 스크롤바를 포함한 완벽 프리미엄 컨테이너 위젯"""
    maximized = pyqtSignal(object)
    
    def __init__(self, title, color="#a6e3a1"):
        super().__init__()
        self.title_str = title
        self.setStyleSheet("""
            QFrame {
                background-color: #181825; 
                border: 1px solid #313244; 
                border-radius: 12px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 8)
        layout.setSpacing(6)
        
        # Header
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Malgun Gothic", 10, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #cdd6f4; border: none; background: transparent;")
        header.addWidget(title_label)
        
        header.addStretch()
        
        self.max_btn = QPushButton("🔍")
        self.max_btn.setFixedSize(24, 24)
        self.max_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.max_btn.setStyleSheet("""
            QPushButton {
                background: #1e1e2e; 
                border: 1px solid #313244; 
                border-radius: 6px; 
                color: #89b4fa;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #313244;
                border-color: #89b4fa;
            }
        """)
        self.max_btn.clicked.connect(lambda: self.maximized.emit(self))
        header.addWidget(self.max_btn)
        
        layout.addLayout(header)
        
        # 차트 위젯 초기화
        self.chart = SimpleChart(color)
        self.chart.setStyleSheet("border: none; background: transparent;")
        layout.addWidget(self.chart, 1)
        
        # 과거 데이터 스캔용 슬릭 스크롤바 조립 (증권사 앱 스타일)
        self.scrollbar = QScrollBar(Qt.Orientation.Horizontal)
        self.scrollbar.setCursor(Qt.CursorShape.SplitHCursor)
        self.scrollbar.setStyleSheet("""
            QScrollBar:horizontal {
                border: none;
                background: #11111b;
                height: 8px;
                margin: 0px 15px 0px 60px; /* 차트 드로잉 영역 폭(left_margin=60, right_margin=15)과 칼정렬 */
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal {
                background: #313244;
                min-width: 30px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #89b4fa;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                border: none;
                background: none;
                width: 0px;
            }
        """)
        self.scrollbar.setRange(0, 0)
        self.scrollbar.setEnabled(False) # 최초 50포인트 적재 전까지는 영리하게 비활성 상태로 상시 노출!
        self.scrollbar.valueChanged.connect(self.on_scrollbar_moved)
        layout.addWidget(self.scrollbar)
        
        # 차트 마우스 휠 동작 -> 스크롤바 자동 연동 (양방향 데이터 바인딩)
        self.chart.scroll_changed.connect(self.on_chart_scrolled)
        
    def add_data(self, val):
        self.chart.add_data(val)
        self.update_scrollbar()
        
    def update_scrollbar(self):
        """데이터 볼륨이 50포인트를 초과할 시 슬라이드 스크롤바 작동 활성화"""
        n = len(self.chart.data)
        if n > self.chart.max_points:
            max_val = n - self.chart.max_points
            self.scrollbar.setEnabled(True)
            self.scrollbar.setRange(0, max_val)
            self.scrollbar.setPageStep(self.chart.max_points)
            
            # 스크롤 락이 아닌 경우 항상 최신 데이터(우측 끝) 유지
            if self.chart.scroll_offset == 0:
                self.scrollbar.blockSignals(True)
                self.scrollbar.setValue(max_val)
                self.scrollbar.blockSignals(False)
            else:
                self.scrollbar.blockSignals(True)
                self.scrollbar.setValue(max_val - self.chart.scroll_offset)
                self.scrollbar.blockSignals(False)
        else:
            self.scrollbar.setEnabled(False)
            self.scrollbar.setRange(0, 0)
            
    def on_scrollbar_moved(self, val):
        """스크롤바 핸들링 시 차트 내부 과거 시계열 스케일로 관성 카메라 동기화 이동"""
        n = len(self.chart.data)
        if n > self.chart.max_points:
            max_val = n - self.chart.max_points
            self.chart.scroll_offset = max_val - val
            self.chart.update()
        else:
            self.chart.scroll_offset = 0
            self.chart.update()
            
    def on_chart_scrolled(self, scroll_offset):
        """차트 영역 마우스 휠 조작 시 하단 스크롤바 조절 노드 물리적 동기화"""
        n = len(self.chart.data)
        if n > self.chart.max_points:
            max_val = n - self.chart.max_points
            self.scrollbar.blockSignals(True)
            self.scrollbar.setValue(max_val - scroll_offset)
            self.scrollbar.blockSignals(False)
