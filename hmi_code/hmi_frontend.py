import json
import socket
import subprocess
import sys
import time

from PyQt6.QtCore import *
from PySide6.QtWidgets import *

STAY_NODE = True
CURRENT_NODE = 'x'


class MainWindow(QMainWindow):
    def __init__(self, parent=None, listenPort=12345):
        super().__init__()
        self.setMinimumSize(600, 200)

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
    """This class is used to listen for incoming broadcast status packets from the nodes for the HMI to display"""

    def run(self, listenPort=12345, sockSize=512):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Create a UDP socket
        sock.bind(('', listenPort))  # Listen on all interfaces on port 12345 for broadcast packets
        while True:
            data, _ = sock.recvfrom(sockSize)
            packet = json.loads(data.decode('utf-8'))

            if CURRENT_NODE in packet['ip']:  # if the packet is from the currently selected node
                del packet['ip']
                print(f"State for Node {CURRENT_NODE} is {packet}")


class PowerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)


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


class NodeSelectionWidget(QWidget):
    def __init__(self):
        super().__init__()

        # Create the combo box and set its items
        self.combo_box = QComboBox()
        self.combo_box.addItems(["Select a Node", "139", "140", "141", "142"])
        self.combo_box.currentIndexChanged.connect(self.combo_box_index_changed)

        self.label = QLabel("Currently viewing:")
        self.layout = QGridLayout()
        self.layout.addWidget(self.label, 0, 0)
        self.layout.addWidget(self.combo_box, 0, 1)
        self.setLayout(self.layout)

    def combo_box_index_changed(self):
        global CURRENT_NODE
        CURRENT_NODE = self.combo_box.currentText()
        print(f"Selected Node: {CURRENT_NODE}")  # Print the selected item's index to the console


if __name__ == '__main__':
    selfIP = socket.gethostbyname(socket.gethostname())
    nodeIPs = ["192.168.137.139", "192.168.137.140", "192.168.137.141", "192.168.137.142", "192.168.137.143"]
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    app.exec()
