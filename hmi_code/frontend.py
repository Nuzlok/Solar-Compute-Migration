import pickle
import socket
import sys
import time
from enum import Enum, auto
from ipaddress import IPv4Address
import wexpect

from customWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

CURRENTLY_SELECTED = 'x'
DEBUG = True
nodeStatuses = {}


class NodeState(Enum):
    IDLE = auto()			# Node is idle and ready to accept
    BUSY = auto()			# Node is busy with processes and cannot accept processes
    MIGRATING = auto()  	# Node is migrating to another and cannot accept processes
    SHUTDOWN = auto()		# Node is shutting down and cannot accept processes

    def __str__(self):
        return self.name


class MainWindow(QMainWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFixedSize(600, 300)
        self.setWindowTitle("Solar Node Monitor")
        self.setWindowIcon(QIcon('solar.jpg'))

        self.title_label = QLabel("Solar Node Monitor", parent=self)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("font-size: 40px; font-weight: bold;")
        self.powerWidget = PowerWidget(parent=self)
        self.manualMode = ManualModeWidget(parent=self)
        self.manualButtons = ManualButtonsWidget(parent=self)
        self.nodeSelector = NodeSelectionWidget(parent=self)

        self.stateText = QLineEdit(self)
        self.stateText.setText('Current State')
        self.stateText.setAlignment(Qt.AlignCenter)
        self.stateText.setReadOnly(True)
        self.stateText.setMinimumHeight(100)
        self.stateText.setStyleSheet("color: grey; font: 24pt; text-align: center; border-radius: 10px; border: 1px solid grey; margin: 10px 20px 10px 20px;")

        self.layout = QGridLayout()  # (parent=self) generates a warning
        self.layout.addWidget(self.title_label, 0, 0, 1, 4)
        self.layout.addWidget(self.nodeSelector, 1, 0, 1, 3)
        self.layout.addWidget(self.powerWidget, 2, 0)
        self.layout.addWidget(self.manualMode, 2, 1)
        self.layout.addWidget(self.stateText, 3, 0)
        self.layout.addWidget(self.manualButtons, 3, 1)
        self.layoutWidget = QWidget()  # (parent=self) generates a warning
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
        global CURRENTLY_SELECTED, nodeStatuses
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Create a UDP socket
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow multiple sockets to use the same PORT number
        sock.settimeout(0.3)  # Set a timeout so the socket doesn't block indefinitely when trying to receive data
        sock.bind(('', listenPort))  # Listen on all interfaces on port 12345 for broadcast packets
        self._running = True

        while self._running:
            try:
                PACKET = pickle.loads(sock.recvfrom(sockSize)[0])

                nodeStatuses[PACKET['ip']] = PACKET, time.time()

                if CURRENTLY_SELECTED in PACKET['ip']:  # TODO: Fix this if statement (if the packet is from the currently selected node). This is a hacky way to do it
                    mWindow.nodeSelector.address.setText(PACKET['ip'])
                    vol, cur = float(PACKET['voltage']), float(PACKET['current'])
                    mWindow.powerWidget.power.setText(f"{(5*vol):=.2f} V  *  {cur:=.2f} A  =  {(5*vol*cur) := .2f} W")
                    mWindow.stateText.setText(str(PACKET['state']))
                    mWindow.manualButtons.shutdownBut.setText("Shutdown" if PACKET['state'] != NodeState.SHUTDOWN else "Switch to IDLE")
                    if PACKET['state'] != NodeState.IDLE and PACKET['state'] != NodeState.SHUTDOWN:
                        mWindow.manualButtons.shutdownBut.setEnabled(False)
                    else:
                        mWindow.manualButtons.shutdownBut.setEnabled(True)
                    if DEBUG:
                        print(f"State for Node {CURRENTLY_SELECTED} is {PACKET}")
            except socket.timeout:
                pass
            except Exception as e:
                print(e)
                pass
        sock.close()


class PowerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.label = QLabel("Input Power: ", parent=parent)

        self.power = QLineEdit('Select a Node', self)
        self.power.setAlignment(Qt.AlignCenter)
        self.power.setStyleSheet("color: grey; border-radius: 10px; border: 1px solid grey;")
        self.power.setReadOnly(True)
        self.power.setToolTip("The current input power to the selected node in Watts")

        self.layout = QHBoxLayout(self)
        self.layout.addWidget(self.label, 0)
        self.layout.addWidget(self.power, 1)
        self.setLayout(self.layout)

"""
# class RefreshWidget(QWidget):
#     def __init__(self, parent=None, size=20):
#         super().__init__(parent=parent)
#
#         self.refresh_button = QPushButton(icon=QIcon('images/refresh.png'), parent=self)
#         self.refresh_button.setIconSize(QSize(size, size))
#         # self.button.clicked.connect(self.refreshNodesList)# FIX THE FUNCTION FIRST
#
#         self.refresh_gif = QMovie("images/refresh.gif")
#         self.refresh_gif.frameChanged.connect(self.update_refresh_icon)
#         self.refresh_button.clicked.connect(self.play_gif)
#
#     def refreshNodesList(self) -> None:
#         \"\"\"
#         # global nodeIPs
#         # nodeIPs = []
#
#         # # -------------------- change so it works in any situation. currently only works when connected to nodes directly on ethernet --------------------
#         # # -------------------- if any other devices is connected to the network, it will be added to the list when it should not --------------------
#         # # -------------------- could be fixed by passively listening for broadcast messages instead. but this way you cant choose offline nodes  ---------
#
#         # output = subprocess.run(['ip', 'route'], capture_output=True, text=True).stdout.splitlines()
#         # gateIP = output[0].split(' ')[2]  # get the gateway ip of the current network
#         # cidr = output[1].split(' ')[0]  # get the cidr of the current network
#
#         # lines = subprocess.run(['sudo', 'arp-scan', cidr, '-x', '-q', '-g'], capture_output=True, text=True).stdout.splitlines()
#         # for line in lines:  # for every found node in the network
#         #     nodeIPs.append(line.split('\t')[0])  # add the ip of that node to the list
#         # print(nodeIPs)
#
#         # if selfIP in nodeIPs:
#         #     nodeIPs.remove(selfIP)  # removing my own ip from the list
#         # if gateIP in nodeIPs:
#         #     nodeIPs.remove(gateIP)  # removing gateway ip from the list
#         \"\"\"
#         pass
#
#     def play_gif(self):
#         if self.refresh_gif.state() == QMovie.Running:
#             self.refresh_gif.stop()
#             self.refresh_button.setIcon(QPixmap("images/refresh.png"))
#         else:
#             self.refresh_gif.start()
#
#     def update_refresh_icon(self):
#         self.refresh_button.setIcon(self.refresh_gif.currentPixmap())
"""

class ManualModeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.label = QLabel("Manual Mode: ")

        self.check = QToggleSwitch(parent=self)
        self.check.toggled.connect(self.on_toggled)
        self.check.setChecked(False)
        self.check.setEnabled(False)
        self.check.setToolTip("Please select a node first")

        self.layout = QHBoxLayout(self)
        self.layout.addWidget(self.label, 0, Qt.AlignRight)
        self.layout.addWidget(self.check, 1)
        self.setLayout(self.layout)

    def on_toggled(self, state):
        mWindow.manualButtons.setEnabled(state)
        # print(f"Manual Mode {'Enabled' if state else 'Disabled'}")

        if state:
            mWindow.manualMode.check.setToolTip("Slide to disable manual mode")
        else:
            mWindow.manualMode.check.setToolTip("Slide to enable manual mode")


class NodeSelectionWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.combo_box = QComboBox()
        self.combo_box.addItems(["Select a Node", "139", "140", "141", "142", "143"])
        self.combo_box.currentIndexChanged.connect(self.combo_box_index_changed)

        # self.refreshButton = RefreshWidget(parent=self)
        # self.refreshButton.setToolTip("Update the nodes available")

        self.label1 = QLabel("Currently viewing:")
        self.label2 = QLabel("IP of Node: ")

        self.address = QLineEdit(self)
        self.address.setText('Select a Node')
        self.address.setReadOnly(True)
        self.address.setAlignment(Qt.AlignCenter)
        self.address.setStyleSheet("color: grey;border-radius: 10px; border: 1px solid grey;")
        self.address.setToolTip("The IP address of the selected node")

        self.layout = QHBoxLayout()
        self.layout.addWidget(self.label1, 0)
        self.layout.addWidget(self.combo_box, 1)
        # self.layout.addWidget(self.refreshButton, 2)
        self.layout.addWidget(self.label2, 3, Qt.AlignRight)
        self.layout.addWidget(self.address, 4)
        self.setLayout(self.layout)

    def combo_box_index_changed(self):
        global CURRENTLY_SELECTED
        CURRENTLY_SELECTED = self.combo_box.currentText()
        mWindow.manualMode.check.setChecked(False)

        if CURRENTLY_SELECTED != "Select a Node":
            self.address.setText('Loading...')
            mWindow.stateText.setText('Loading...')
            mWindow.powerWidget.power.setText('Loading...')
            mWindow.manualMode.check.setEnabled(True)

            # Even if the slider is checked, the below text will be read if index is changed (we have made it so
            # that slider becomes unchecked every time "combo_box_index_changed" is called so we should be fine)
            mWindow.manualMode.check.setToolTip("Slide to enable manual mode")
        else:
            self.address.setText('Select a Node')
            mWindow.stateText.setText('Select a Node')
            mWindow.powerWidget.power.setText('Select a Node')
            mWindow.manualMode.check.setChecked(False)
            mWindow.manualMode.check.setEnabled(False)
            mWindow.manualMode.check.setToolTip("Please select a node first")

        print(f"Selected Node: {CURRENTLY_SELECTED}")  # Print the selected item's index to the console


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
        
        # set the button actions
        self.transferBut.clicked.connect(lambda: self.migrate(f"192.168.137.{CURRENTLY_SELECTED}"))
        self.takeNewPBut.clicked.connect(lambda: self.takeNew(f"192.168.137.{CURRENTLY_SELECTED}"))
        self.saveProcBut.clicked.connect(lambda: self.saveProc(f"192.168.137.{CURRENTLY_SELECTED}"))
        self.shutdownBut.clicked.connect(lambda: self.shutdown(f"192.168.137.{CURRENTLY_SELECTED}"))

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

    def migrate(self, selected_ip, user="pi", password="pi"):
        self.command(f'touch /home/{user}/force_migrate.txt', selected_ip, user, password)

    def takeNew(self, selected_ip, user="pi", password="pi"):
        self.command(f'touch /home/{user}/startflag.txt', selected_ip, user, password)

    def saveProc(self, selected_ip, user="pi", password="pi"):
        self.command(f'touch /home/{user}/force_dump.txt', selected_ip, user, password)

    def shutdown(self, selected_ip, user="pi", password="pi"):
        # command = 'sudo -S shutdown now'
        # print(f"ssh {user}@{selected_ip} '{command}'")
        # child = wexpect.spawn(f"ssh {user}@{selected_ip} {command}", timeout=30)
        # child.expect([f"{user}@{selected_ip}'s password:"], timeout=5)
        # child.sendline(password)
        # child.expect([f"\[sudo\] password for {user}:"], timeout=5)
        # child.sendline(password)
        # child.expect(wexpect.EOF)
        if self.shutdownBut.text() == "Shutdown":
            self.command(f'touch /home/{user}/force_shutdown.txt', selected_ip, user, password)
        else:
            self.command(f'touch /home/{user}/force_idle.txt', selected_ip, user, password)
        

    def command(self, command, selected_ip, user, password):
        print(f"ssh {user}@{selected_ip} '{command}'")
        child = wexpect.spawn(f"ssh {user}@{selected_ip} '{command}'", timeout=30)
        child.expect([f"{user}@{selected_ip}'s password:"])
        child.sendline(password)
        child.expect(wexpect.EOF)


if __name__ == '__main__':
    if 'darkmode' in sys.argv:
        sys.argv += ['-platform', 'windows:darkmode=2']
    app = QApplication(sys.argv)
    mWindow = MainWindow()
    mWindow.show()
    app.exec()
