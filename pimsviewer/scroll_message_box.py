from PyQt5.QtWidgets import (QWidget, QDialog, QMessageBox, QScrollArea, QVBoxLayout, QLabel)

class ScrollMessageBox(QMessageBox):
    def __init__(self, items, *args, **kwargs):
        super(ScrollMessageBox, self).__init__(*args, **kwargs)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)

        self.content = QWidget()

        scroll.setWidget(self.content)

        layout = QVBoxLayout(self.content)
        for item in items:
            layout.addWidget(QLabel(item, self))

        self.layout().addWidget(scroll, 0, 0, 1, self.layout().columnCount())
        self.setStyleSheet("QScrollArea{min-width:300 px; min-height: 400px}")
        self.show()
