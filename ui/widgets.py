from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class MetricCard(QFrame):
    """顶部指标卡片。"""

    def __init__(self, title: str, value: str = "-", parent=None):
        super().__init__(parent)
        self.setObjectName("MetricCard")
        self.title_label = QLabel(title)
        self.title_label.setObjectName("MetricTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("MetricValue")
        self.value_label.setWordWrap(True)
        self.value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)
