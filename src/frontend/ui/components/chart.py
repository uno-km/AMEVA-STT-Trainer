from src.frontend.ui.core.qt import *

class SimpleChart(QWidget):
    """QPainter를 이용한 커스텀 선 그래프 위젯 (스크롤 및 눈금 지원)"""
    def __init__(self, color="#a6e3a1"):
        super().__init__()
        self.data = []
        self.max_points = 50
        self.line_color = QColor(color)
        self.scroll_offset = 0  # 과거 데이터 조회를 위한 오프셋
        
    def add_data(self, value):
        self.data.append(value)
        # 스크롤 중이 아니면 최신 데이터를 따라감
        if self.scroll_offset == 0 and len(self.data) > self.max_points:
            # We don't pop anymore to keep history, but we only draw the window
            pass
        self.update()

    def wheelEvent(self, event):
        """마우스 휠로 과거 데이터 스크롤"""
        delta = event.angleDelta().y()
        if delta > 0:
            self.scroll_offset = min(self.scroll_offset + 5, max(0, len(self.data) - self.max_points))
        else:
            self.scroll_offset = max(self.scroll_offset - 5, 0)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        
        # Draw background grid and labels
        painter.setPen(QPen(QColor("#313244"), 1, Qt.PenStyle.DashLine))
        painter.setFont(self.font())
        for i in range(1, 4):
            y = int(h * i / 4)
            painter.drawLine(0, y, w, y)
        
        if not self.data: return
        
        # Calculate view window
        start_idx = max(0, len(self.data) - self.max_points - self.scroll_offset)
        end_idx = start_idx + self.max_points
        view_data = self.data[start_idx:end_idx]
        
        if not view_data: return
        
        max_val = max(view_data) if max(view_data) > 0 else 1
        min_val = min(view_data)
        
        # Draw min/max labels
        painter.setPen(QPen(QColor("#6c7086")))
        painter.drawText(5, 15, f"{max_val:.2f}")
        painter.drawText(5, h - 5, f"{min_val:.2f}")
        
        # Draw line
        path = QPainterPath()
        point_spacing = w / (self.max_points - 1) if self.max_points > 1 else 0
        
        for i, val in enumerate(view_data):
            x = i * point_spacing
            # Normalize y between 10% and 90% height
            norm_y = (val - min_val) / (max_val - min_val) if max_val > min_val else 0.5
            y = h - (norm_y * h * 0.8) - (h * 0.1)
            
            if i == 0: path.moveTo(x, y)
            else: path.lineTo(x, y)
            
        painter.setPen(QPen(self.line_color, 2))
        painter.drawPath(path)

class ChartWidget(QFrame):
    """제목, 최대화 버튼, 차트를 포함한 컨테이너 위젯"""
    maximized = pyqtSignal(object)
    
    def __init__(self, title, color="#a6e3a1"):
        super().__init__()
        self.title_str = title
        self.setStyleSheet("background-color: #11111b; border: 1px solid #313244; border-radius: 5px;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Header
        header = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #cdd6f4; font-weight: bold; border: none;")
        header.addWidget(title_label)
        
        self.max_btn = QPushButton("🔍")
        self.max_btn.setFixedSize(20, 20)
        self.max_btn.setStyleSheet("background: transparent; border: none; color: #89b4fa;")
        self.max_btn.clicked.connect(lambda: self.maximized.emit(self))
        header.addWidget(self.max_btn)
        
        layout.addLayout(header)
        
        self.chart = SimpleChart(color)
        layout.addWidget(self.chart)

    def add_data(self, val):
        self.chart.add_data(val)
