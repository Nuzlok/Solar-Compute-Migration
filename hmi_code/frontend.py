import json
import socket
import subprocess
import sys
import time

from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

NODE_STATUS = {'ip': 'x'}
CURRENT_NODE = 'x'
DEBUG = True


class MainWindow(QMainWindow):
    def __init__(self, listenPort=12345, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMinimumSize(600, 200)

        self.title_label = QLabel("Migration Assistant")
        self.title_label.setStyleSheet("font-size: 40px; font-weight: bold;")
        self.nodeSelector = NodeSelectionWidget()
        self.powerWidget = PowerWidget()

        self.manualMode = ManualModeWidget()

        self.layout = QGridLayout()
        self.layout.addWidget(self.title_label, 0, 0, 1, 4)
        self.layout.addWidget(self.nodeSelector, 1, 0, 1, 3)
        self.layout.addWidget(self.powerWidget, 2, 0)
        self.layout.addWidget(self.manualMode, 2, 1)
        self.layoutWidget = QWidget()
        self.layoutWidget.setLayout(self.layout)
        self.setCentralWidget(self.layoutWidget)

        self.worker = asyncWorker()
        with self.worker:
            self.worker.start()


class asyncWorker(QThread):
    """This class is used to listen for incoming broadcast status packets from the nodes for the HMI to display"""

    def stop(self):
        self.KeepRunning = False

    def run(self, listenPort=12345, sockSize=512):
        global CURRENT_NODE, NODE_STATUS
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Create a UDP socket
        sock.bind(('', listenPort))  # Listen on all interfaces on port 12345 for broadcast packets
        self.KeepRunning = True
        print(f"Worker thread started {self.KeepRunning}")
        while self.KeepRunning:
            packet = json.loads(sock.recvfrom(sockSize)[0].decode('utf-8'))

            if CURRENT_NODE in packet['ip']:  # TODO: Fix this (if the packet is from the currently selected node). This is a hacky way to do it
                NODE_STATUS = packet
                mWindow.nodeSelector.address.setText(NODE_STATUS['ip'])
                mWindow.powerWidget.power.setText(f"{NODE_STATUS['current']*NODE_STATUS['voltage']} W")
                if DEBUG:
                    print(f"State for Node {CURRENT_NODE} is {packet}")

        print("Worker thread stopped")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        # self.wait()


class QToggleSwitch(QCheckBox):
    """ A custom toggle switch widget. Copied from: https://www.youtube.com/watch?v=NnJFi285s3M"""

    def __init__(self, width=60, bg_color="#777", circle_color="#DDD",  active_color="#599afe", animation_curve=QEasingCurve.Type.OutCirc):
        super().__init__()

        self.setFixedSize(width, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._bg_color = bg_color
        self._circle_color = circle_color
        self._active_color = active_color

        self._circle_position = 3
        self.animation = QPropertyAnimation(self, b"circle_position", self)
        self.animation.setEasingCurve(animation_curve)
        self.animation.setDuration(200)

        self.stateChanged.connect(self.start_transition)

    @Property(float)
    def circle_position(self):
        return self._circle_position

    @circle_position.setter
    def circle_position(self, pos):
        self._circle_position = pos
        self.update()

    def start_transition(self, value):
        self.animation.stop()
        self.animation.setEndValue(self.width() - 26 if value else 3)
        if DEBUG:
            print(f'Manual Mode isChecked: {self.isChecked()}')
        self.animation.start()

    def Error(self):
        self.setCheckState(Qt.Unchecked)
        self.start_transition

    def paintEvent(self, _: QPaintEvent):
        p = QPainter()
        p.begin(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)

        p.setBrush(QColor(self._active_color if self.isChecked() else self._bg_color))
        p.drawRoundedRect(0, 0, self.width(), self.height(), self.height() / 2, self.height() / 2)
        p.setBrush(QColor(self._circle_color))
        p.drawEllipse(self._circle_position, 3, 22, 22)
        p.end()

    def hitButton(self, pos: QPoint) -> bool:
        return self.contentsRect().contains(pos)


class PowerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.label = QLabel("Input Power: ")

        self.power = QLineEdit(self)
        self.power.setText('Select a Node')
        self.power.setReadOnly(True)
        self.power.setStyleSheet("color: grey; ")

        self.layout = QHBoxLayout()
        self.layout.addWidget(self.label, 0)
        self.layout.addWidget(self.power, 1)
        self.setLayout(self.layout)


class RefreshWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

    def refreshNodesList(self) -> None:  # could potentially change so instead of active scan, wait and listen for broadcast messages instead.
        global nodeIPs
        nodeIPs = []

        output = subprocess.run(['ip', 'route'], capture_output=True, text=True).stdout.splitlines()
        gateIP = output[0].split(' ')[2]  # get the gateway ip of the current network
        cidr = output[1].split(' ')[0]  # get the cidr of the current network

        lines = subprocess.run(['sudo', 'arp-scan', cidr, '-x', '-q', '-g'], capture_output=True, text=True).stdout.splitlines()
        for line in lines:  # for every found node in the network
            nodeIPs.append(line.split('\t')[0])  # add the ip of that node to the list
        print(nodeIPs)

        if selfIP in nodeIPs:
            nodeIPs.remove(selfIP)  # removing my own ip from the list
        if gateIP in nodeIPs:
            nodeIPs.remove(gateIP)  # removing gateway ip from the list


class ManualModeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.label = QLabel("Manual Mode: ")

        self.check = QToggleSwitch()

        self.layout = QHBoxLayout()
        self.layout.addWidget(self.label, 0, Qt.AlignRight)
        self.layout.addWidget(self.check, 1)
        self.setLayout(self.layout)


class NodeSelectionWidget(QWidget):
    def __init__(self):
        super().__init__()

        # Create the combo box and set its items
        self.combo_box = QComboBox()
        self.combo_box.addItems(["Select a Node", "139", "140", "141", "142"])
        self.combo_box.currentIndexChanged.connect(self.combo_box_index_changed)

        self.label = QLabel("Currently viewing:")

        self.label2 = QLabel("IP Address of Selected Node: ")
        self.address = QLineEdit(self)
        self.address.setText('Select a Node')
        self.address.setReadOnly(True)
        self.address.setStyleSheet("color: grey;")

        self.layout = QHBoxLayout()
        self.layout.addWidget(self.label, 0)
        self.layout.addWidget(self.combo_box, 1)
        self.layout.addWidget(self.label2, 3, Qt.AlignRight)
        self.layout.addWidget(self.address, 4)
        self.setLayout(self.layout)

    def combo_box_index_changed(self):
        global CURRENT_NODE
        CURRENT_NODE = self.combo_box.currentText()
        if CURRENT_NODE != "Select a Node":
            self.address.setText('Loading...')
        else:
            self.address.setText('Select a Node')
        print(f"Selected Node: {CURRENT_NODE}")  # Print the selected item's index to the console


if __name__ == '__main__':
    selfIP = socket.gethostbyname(socket.gethostname())
    nodeIPs = ["192.168.137.139", "192.168.137.140", "192.168.137.141", "192.168.137.142", "192.168.137.143"]
    app = QApplication(sys.argv)
    mWindow = MainWindow()
    mWindow.show()
    app.exec()
