from src.frontend.ui.core.qt import *

class ExplorerPanel(QWidget):
    """파일 탐색기 및 검색 기능을 담당하는 컴포넌트"""
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 0)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 파일/폴더 검색 (디바운스)...")
        self.search_bar.setStyleSheet(f"padding: 8px; background-color: {ctx.get_color('bg_dark')}; border: 1px solid {ctx.get_color('border')}; border-radius: 4px;")
        layout.addWidget(self.search_bar)
        
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setStyleSheet(f"background-color: {ctx.get_color('bg_panel')}; border: 1px solid {ctx.get_color('border')};")
        layout.addWidget(self.tree)
        
        # Debounce Timer (0.5s)
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.filter_tree)
        self.search_bar.textChanged.connect(lambda: self.search_timer.start(500))

    def update_data(self, files_data):
        self.tree.clear()
        if not files_data: return
        
        def add_items_recursive(parent_item, items):
            for item in items:
                child = QTreeWidgetItem(parent_item, [item["name"]])
                if item.get("is_dir"):
                    child.setForeground(0, QColor(self.ctx.get_color('warning')))
                    if "children" in item:
                        add_items_recursive(child, item["children"])
                else:
                    child.setData(0, Qt.ItemDataRole.UserRole, item["path"])

        for category, items in files_data.items():
            cat_item = QTreeWidgetItem(self.tree, [category.upper()])
            cat_item.setForeground(0, QColor(self.ctx.get_color('accent')))
            add_items_recursive(cat_item, items)
            cat_item.setExpanded(True)

    def filter_tree(self):
        search_text = self.search_bar.text().lower()
        def filter_item(item):
            item_text = item.text(0).lower()
            any_child_visible = False
            for i in range(item.childCount()):
                if filter_item(item.child(i)): any_child_visible = True
            is_visible = (search_text in item_text) or any_child_visible
            item.setHidden(not is_visible)
            if search_text and is_visible: item.setExpanded(True)
            return is_visible

        for i in range(self.tree.topLevelItemCount()):
            filter_item(self.tree.topLevelItem(i))
