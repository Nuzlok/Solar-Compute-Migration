import json
import socket
import sys
import time

from PyQt6.QtCore import Qt, QThread, QTimer
from PySide6.QtWidgets import *


class MainWindow(QMainWindow):
    def __init__(self, parent=None, listenPort=12345):
        super().__init__()
        self.setMinimumSize(600, 600)

        title_label = QLabel("Migration Assistant")
        title_label.setStyleSheet("font-size: 40px; font-weight: bold;")
        # title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        nodeSelector = NodeSelectionWidget()

        layout = QGridLayout()
        layout.addWidget(title_label, 0, 0, 1, 4)
        layout.addWidget(nodeSelector, 1, 0)
        layoutWidget = QWidget()
        layoutWidget.setLayout(layout)
        self.setCentralWidget(layoutWidget)

        self.worker = asyncWorker()
        self.worker.start()


class asyncWorker(QThread):
    def run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Create a UDP socket
        sock.bind(('', 12345))  # Listen on all interfaces on port 12345 for broadcast packets
        while True:
            data, _ = sock.recvfrom(512)
            packet = json.loads(data.decode('utf-8'))
            ip = packet['ip']
            del packet['ip']
            print(f"State for {ip} is {packet}")
            # time.sleep(0.4)


class PowerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)


class NodeSelectionWidget(QWidget):
    def __init__(self):
        super().__init__()

        # Create the combo box and set its items
        self.combo_box = QComboBox()
        self.combo_box.addItems(["Select Node", "Item 1", "Item 2", "Item 3", "Item 4"])
        self.combo_box.currentIndexChanged.connect(self.combo_box_index_changed)

        self.label = QLabel("Currently viewing:")
        self.layout = QGridLayout()
        self.layout.addWidget(self.label, 0, 0)
        self.layout.addWidget(self.combo_box, 0, 1)
        self.setLayout(self.layout)

    def combo_box_index_changed(self):
        # Print the selected item's index to the console
        print(self.combo_box.currentIndex())


if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    app.exec()
