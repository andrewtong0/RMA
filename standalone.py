# from PyQt5.QtWidgets import QApplication, QLabel
# app = QApplication([])
# label = QLabel('Hello World!')
# label.show()
# app.exec_()

from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout
app = QApplication([])
window = QWidget()
layout = QVBoxLayout()
layout.addWidget(QPushButton('Top'))
layout.addWidget(QPushButton('Bottom'))
window.setLayout(layout)
window.show()
app.exec_()
