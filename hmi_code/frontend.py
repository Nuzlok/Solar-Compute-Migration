import json
import socket
import sys

from customWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

CURRENT_NODE = 'x'
DEBUG = True


class MainWindow(QMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.setMinimumSize(600, 300)
        self.setFixedSize(600, 300)     # Resizing the window horizontally breaks the alignment of the "resize button"
        self.setWindowTitle("Migration Assistant")

        self.title_label = QLabel("Migration Assistant", parent=self)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-size: 40px; font-weight: bold;")
        self.nodeSelector = NodeSelectionWidget(parent=self)
        self.powerWidget = PowerWidget(parent=self)
        self.manualMode = ManualModeWidget(parent=self)
        self.manualButtons = ManualButtonsWidget(parent=self)
        self.stateText = CurrentStateWidget(parent=self)

        self.layout = QGridLayout()
        # self.layout = QGridLayout(parent=self)        # It appears (parent=self) generates a warning
        self.layout.addWidget(self.title_label, 0, 0, 1, 4)
        self.layout.addWidget(self.nodeSelector, 1, 0, 1, 3)
        self.layout.addWidget(self.powerWidget, 2, 0)
        self.layout.addWidget(self.manualMode, 2, 1)
        self.layout.addWidget(self.stateText, 3, 0)
        self.layout.addWidget(self.manualButtons, 3, 1)
        self.layoutWidget = QWidget()
        # self.layoutWidget = QWidget(parent=self)      # It appears (parent=self) generates a warning
        self.layoutWidget.setLayout(self.layout)
        self.setCentralWidget(self.layoutWidget)

        self.worker = asyncWorker()
        self.worker.start()

    def closeEvent(self, event) -> None:
        self.worker.stop()
        self.worker.wait(deadline=500)
        return super().closeEvent(event)


class asyncWorker(QThread):
    """This class is used to listen for incoming broadcast status packets from the nodes for the HMI to display"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._running = True

    def stop(self):
        self._running = False

    def run(self, listenPort=12345, sockSize=512):
        global CURRENT_NODE
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Create a UDP socket
        sock.settimeout(0.3)  # Set a timeout so the socket doesn't block indefinitely when trying to receive data
        sock.bind(('', listenPort))  # Listen on all interfaces on port 12345 for broadcast packets
        self._running = True

        while self._running:
            try:
                packet = json.loads(sock.recvfrom(sockSize)[0].decode('utf-8'))
                if CURRENT_NODE in packet['ip']:  # TODO: Fix this if statement (if the packet is from the currently selected node). This is a hacky way to do it
                    mWindow.nodeSelector.address.setText(packet['ip'])
                    mWindow.powerWidget.power.setText(f"{packet['current']*packet['voltage']} W")
                    mWindow.stateText.stateText.setText(packet['state'])
                    if DEBUG:
                        print(f"State for Node {CURRENT_NODE} is {packet}")
            except socket.timeout:
                pass
            except Exception as e:
                print(e)
                pass


class PowerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.label = QLabel("Input Power: ", parent=parent)

        self.power = QLineEdit('Select a Node', self)
        self.power.setAlignment(Qt.AlignCenter)
        self.power.setStyleSheet("color: grey; border-radius: 10px; border: 1px solid grey;")
        self.power.setReadOnly(True)

        self.layout = QHBoxLayout(self)
        self.layout.addWidget(self.label, 0)
        self.layout.addWidget(self.power, 1)
        self.setLayout(self.layout)


class RefreshWidget(QWidget):
    def __init__(self, parent=None, size=20):
        super().__init__(parent=parent)

        self.button = QPushButton(icon=QIcon('images/refresh.png'), parent=self)
        self.button.setIconSize(QSize(size, size))
        # self.button.clicked.connect(self.refreshNodesList)# FIX THE FUNCTION FIRST

        self.movie = QMovie("images/refresh.gif")
        self.movie.frameChanged.connect(self.update_icon)
        self.button.clicked.connect(self.play_gif)

    def refreshNodesList(self) -> None:
        """
        # global nodeIPs
        # nodeIPs = []

        # # -------------------- change so it works in any situation. currently only works when connected to nodes directly on ethernet --------------------
        # # -------------------- if any other devices is connected to the network, it will be added to the list when it should not --------------------
        # # -------------------- could be fixed by passively listening for broadcast messages instead. but this way you cant choose offline nodes  ---------

        # output = subprocess.run(['ip', 'route'], capture_output=True, text=True).stdout.splitlines()
        # gateIP = output[0].split(' ')[2]  # get the gateway ip of the current network
        # cidr = output[1].split(' ')[0]  # get the cidr of the current network

        # lines = subprocess.run(['sudo', 'arp-scan', cidr, '-x', '-q', '-g'], capture_output=True, text=True).stdout.splitlines()
        # for line in lines:  # for every found node in the network
        #     nodeIPs.append(line.split('\t')[0])  # add the ip of that node to the list
        # print(nodeIPs)

        # if selfIP in nodeIPs:
        #     nodeIPs.remove(selfIP)  # removing my own ip from the list
        # if gateIP in nodeIPs:
        #     nodeIPs.remove(gateIP)  # removing gateway ip from the list
        """
        pass

    def play_gif(self):
        if self.movie.state() == QMovie.Running:
            self.movie.stop()
            self.button.setIcon(QPixmap("images/refresh.png"))
        else:
            self.movie.start()

    def update_icon(self):
        self.button.setIcon(self.movie.currentPixmap())


class ManualModeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.label = QLabel("Manual Mode: ")

        self.check = QToggleSwitch(parent=self)
        self.check.toggled.connect(self.on_toggled)

        self.layout = QHBoxLayout(self)
        self.layout.addWidget(self.label, 0, Qt.AlignRight)
        self.layout.addWidget(self.check, 1)
        self.setLayout(self.layout)

    def on_toggled(self, state):
        mWindow.manualButtons.setEnabled(state)
        # print(f"Manual Mode {'Enabled' if state else 'Disabled'}")


class NodeSelectionWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        # Create the combo box and set its items
        self.combo_box = QComboBox()
        self.combo_box.addItems(["Select a Node", "139", "140", "141", "142"])
        self.combo_box.currentIndexChanged.connect(self.combo_box_index_changed)
        # self.combo_box.setStyleSheet("color: grey; border-radius: 1px; border: 1px solid grey;")

        self.refreshButton = RefreshWidget(parent=self)

        self.label1 = QLabel("Currently viewing:")
        self.label2 = QLabel("IP of Node: ")

        self.address = QLineEdit(self)
        self.address.setText('Select a Node')
        self.address.setReadOnly(True)
        self.address.setAlignment(Qt.AlignCenter)
        self.address.setStyleSheet("color: grey;border-radius: 10px; border: 1px solid grey;")

        self.layout = QHBoxLayout()
        self.layout.addWidget(self.label1, 0)
        self.layout.addWidget(self.combo_box, 1)
        self.layout.addWidget(self.refreshButton, 2)
        self.layout.addWidget(self.label2, 3, Qt.AlignRight)
        self.layout.addWidget(self.address, 4)
        self.setLayout(self.layout)

    def combo_box_index_changed(self):
        global CURRENT_NODE
        CURRENT_NODE = self.combo_box.currentText()
        if CURRENT_NODE != "Select a Node":
            self.address.setText('Loading...')
            mWindow.stateText.stateText.setText('Loading...')
            mWindow.powerWidget.power.setText('Loading...')
        else:
            self.address.setText('Select a Node')
            mWindow.stateText.stateText.setText('Select a Node')
            mWindow.powerWidget.power.setText('Select a Node')
        print(f"Selected Node: {CURRENT_NODE}")  # Print the selected item's index to the console


class ManualButtonsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.buttonsGroup = []

        # Create the buttons
        self.transferBut = self.createButtonTemplate("Transfer", bColor="grey")
        self.takeNewPBut = self.createButtonTemplate("Take New Process")
        self.saveProcBut = self.createButtonTemplate("Save Process")
        self.shutdownBut = self.createButtonTemplate(label="Shutdown", bColor="red")

        # Create the layout and add the buttons to it in a 2x2 grid
        self.layout = QGridLayout()
        self.layout.addWidget(self.transferBut, 0, 0)
        self.layout.addWidget(self.takeNewPBut, 0, 1)
        self.layout.addWidget(self.saveProcBut, 1, 0)
        self.layout.addWidget(self.shutdownBut, 1, 1)

        # Set the spacing property of the layout to add space between the buttons
        self.layout.setSpacing(10)
        self.setLayout(self.layout)

    def createButtonTemplate(self, label, style='color: #ffffff; border-radius: 8px; border: 1px solid grey;', height=30, bColor='#6aa84f') -> QPushButton:
        temp = QPushButton(label, parent=self)
        # temp.setStyleSheet(f"background-color: {bColor}; {style}")
        temp.setMinimumHeight(height)
        temp.setEnabled(False)
        self.buttonsGroup.append(temp)
        return temp

    def setEnabled(self, state):
        for button in self.buttonsGroup:
            button.setEnabled(state)


class CurrentStateWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.stateText = QLineEdit(self)
        self.stateText.setText('Current State')
        self.stateText.setAlignment(Qt.AlignCenter)
        self.stateText.setReadOnly(True)
        self.stateText.setMinimumHeight(100)
        self.stateText.setStyleSheet("color: grey; font: 24pt; text-align: center; border-radius: 10px; border: 1px solid grey;")

        self.layout = QHBoxLayout()
        self.layout.addWidget(self.stateText, 1)
        self.setLayout(self.layout)

    def resizeEvent(self, event):
        pixmap = QPixmap(self.size())
        painter = QPainter(pixmap)
        painter.fillRect(pixmap.rect(), QColor(255, 255, 255))
        painter.setBrush(QColor(0, 0, 0))
        painter.drawRoundedRect(pixmap.rect(), 25, 25)
        self.setMask(pixmap.mask())
        painter.end()
        # self.stateText.setMinimumHeight(self.height() - 20)


if __name__ == '__main__':
    selfIP = socket.gethostbyname(socket.gethostname())
    nodeIPs = ["192.168.137.139", "192.168.137.140", "192.168.137.141", "192.168.137.142", "192.168.137.143"]
    if 'darkmode' in sys.argv:
        sys.argv += ['-platform', 'windows:darkmode=2']
    app = QApplication(sys.argv)
    mWindow = MainWindow()
    mWindow.show()
    app.exec()
