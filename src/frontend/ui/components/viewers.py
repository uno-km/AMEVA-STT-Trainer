import csv
from src.frontend.ui.core.qt import *

class CSVViewer(QTableWidget):
    """CSV 데이터를 격자 형태로 보여주는 범용 컴포넌트"""
    def __init__(self, ctx, file_path=None):
        super().__init__()
        self.ctx = ctx
        self.setStyleSheet(f"background-color: {ctx.get_color('bg_main')}; color: {ctx.get_color('text')}; gridline-color: {ctx.get_color('border')};")
        self.horizontalHeader().setStyleSheet(f"background-color: {ctx.get_color('border')}; color: {ctx.get_color('text')};")
        
        if file_path:
            self.load_csv(file_path)

    def load_csv(self, file_path):
        try:
            with open(file_path, newline='', encoding='utf-8') as f:
                reader = list(csv.reader(f))
                if not reader: return
                
                self.setRowCount(len(reader))
                self.setColumnCount(len(reader[0]))
                self.setHorizontalHeaderLabels(reader[0])
                
                for row_idx, row_data in enumerate(reader[1:]):
                    for col_idx, cell_data in enumerate(row_data):
                        self.setItem(row_idx, col_idx, QTableWidgetItem(cell_data))
                
                self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        except Exception as e:
            print(f"CSV Load Error: {e}")
