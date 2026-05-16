from PyQt6 import QtWidgets, QtCore, QtGui
from src.frontend.client.api_client import api_client

class UIContext(QtCore.QObject):
    """
    중앙 바인딩 객체 - PyQt6 모듈 자체를 바인딩하여 
    하위 컴포넌트에서 임포트 없이 라이브러리를 쓸 수 있게 합니다.
    """
    # 글로벌 이벤트 버스
    task_started = QtCore.pyqtSignal(str)
    logs_updated = QtCore.pyqtSignal(list)
    
    def __init__(self):
        super().__init__()
        # 라이브러리 통째로 바인딩 (W: Widgets, C: Core, G: Gui)
        self.W = QtWidgets
        self.C = QtCore
        self.G = QtGui
        
        self.api = api_client
        
        # 디자인 테마 바인딩
        self.theme = {
            "bg_main": "#1e1e2e",
            "bg_dark": "#11111b",
            "bg_panel": "#181825",
            "border": "#313244",
            "accent": "#89b4fa",
            "success": "#a6e3a1",
            "error": "#f38ba8",
            "warning": "#f9e2af",
            "text": "#cdd6f4",
            "text_dim": "#6c7086"
        }
        
        # 폰트 바인딩 (한글 깨짐 방지를 위해 맑은 고딕 사용)
        self.fonts = {
            "main": self.G.QFont("Malgun Gothic", 10),
            "title": self.G.QFont("Malgun Gothic", 14, self.G.QFont.Weight.Bold),
            "log": self.G.QFont("Malgun Gothic", 10),
            "small": self.G.QFont("Malgun Gothic", 9)
        }
    
    def get_color(self, key):
        return self.theme.get(key, "#ffffff")
