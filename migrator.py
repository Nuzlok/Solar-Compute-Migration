import os
import pickle
import random
import socket
import subprocess
import sys
import threading
import time
from enum import Enum, auto
from ipaddress import IPv4Address


class State(Enum):
    IDLE = auto()			# Node is idle and ready to accept
    BUSY = auto()			# Node is busy with processes and cannot accept processes
    MIGRATING = auto()  	# Node is migrating to another and cannot accept processes
    SHUTDOWN = auto()		# Node is shutting down and cannot accept processes


selfState = {"ip": "", "status": "online", "state": State.IDLE, "current": 0, "voltage": 0, "manual": 'false'}
uniqueOtherNodeStatuses = {}
nodeIPaddrs = []
processID = ""
isManualCMD = ""
EXIT = False


class Process:
    # TODO: Implement Process class.
    # Process class.
    # Contains all the information about a process.
    # This class is used to control the process.
    pass


def handlePolling():
    """Respond to polling from other nodes with state information"""
    # *TCP current state to polling node*
    pass


def waitForProcessCMD() -> tuple:
    return True, "process"


def startProcessThread(proc):
    pass


def handleMigration():
    pass


def handleReboot():
    pass


def handleShutdown():
    pass


def readVoltagefromGPIO() -> float:
    """Read voltage from GPIO"""
    return 0.0


def readCurrentfromGPIO() -> float:
    """Read current from GPIO"""
    return 0.0


def isLossOfPower() -> bool:
    """Decide when node is losing power"""
    voltage = readVoltagefromGPIO()
    current = readCurrentfromGPIO()
    threshold = 0.5
    return (voltage < threshold or current < threshold)


def startProcessThread(process):
    """Handle starting a process"""
    # If no checkpoint
    # *Start Process in separate thread*
    # Else if checkpoint
    # *Start process in separate thread and resume from checkpoint*
    pass


def NetworkScan() -> list:
    """Scan network ping scan for available nodes"""
    selfIP = socket.gethostbyname(socket.gethostname())
    gateway, cidrConf = subprocess.run(['ip', 'route'], capture_output=True, text=True).stdout.splitlines()  # get the network configuration of the node
    gateIP = gateway.split(' ')[2]  # get the gateway ip of the current network from the network configuration
    cidrIP = cidrConf.split(' ')[0]  # get the full cidr of the current network from the network configuration

    nodeIPs = []
    lines = subprocess.run(['sudo', 'arp-scan', cidrIP, '-x', '-q', '-g'], capture_output=True, text=True).stdout.splitlines()
    for line in lines:  # for every found node in the network
        nodeIPs.append(line.split('\t')[0])  # add the ip of that node to the list

    if selfIP in nodeIPs:
        nodeIPs.remove(selfIP)  # removing my own ip from the list
    if gateIP in nodeIPs:
        nodeIPs.remove(gateIP)  # removing gateway ip from the list
    return nodeIPs


def manualInput(input) -> bool:
    """Handle manual input from user"""
    return False


def waitForMigrateCMD() -> bool:
    """
    Handle migrate command. Returns true if the process should be migrated.
    Migration is triggered by a loss of power or a manual migate command through the HMI.
    """
    if isLossOfPower():  # Check for loss of power or manual input command
        return True
    elif manualInput():  # Check for manual input command from HMI
        return True
    return False


def sendFinishTransferFlag(username="pi", ip="1", password="pi", path=""):
    result = subprocess.run(["ssh", "-t", f"{username}@{ip}", "-p", f"{password}", f"touch {path}; exit"], stdout=subprocess.PIPE)
    if result.returncode == 0:
        print("File updated successfully")
    else:
        print("Failed to update file")


def pollNodeforState(address: str) -> str:
    """
    Poll node at given address to get state.
    Used to confirm node status before migrating process to it.
    """
    # *TCP address for Node State*
    statefromNode = State.IDLE
    return statefromNode


def waitForProcessCMD():
    # #Check specified directory for files
    # Process = (check directory, if not empty, then it should contain a process and checkpoint)
    # If Process != none
    # Return Process, true
    # Else
    # Return none, false
    pass


def CheckpointandSaveProcessToDisk(processID: int, proc: Process):
    """Handle case of no available nodes, checkpoint process to current working directory"""
    # *Run bash Script to checkpoint node and Save to receiving directory on current node*
    # *That way, on startup any files inside the directory will immediately be restored from
    # Checkpoint and resumed on system*
    pass


def checkpointAndMigrateProcessToNode(processID: int, proc: Process, ipToSend):
    # Handle checkpointing and migration
    # *Run bash Script to checkpoint node and SCP to address in specific directory*
    # *Delete process and supporting files on current node*
    pass


def migrateProcessToAvaliableNode(processID: int, proc: Process):
    global selfState
    ipToSend = None
    for address in nodeIPaddrs:
        selfState = pollNodeforState(address)
        if selfState == State.IDLE:
            if ipToSend == None:
                ipToSend = address
            else:
                # * Possible comparison for other factors like time, weather, etc.*
                ipToSend = address
    if ipToSend == None:
        CheckpointandSaveProcessToDisk(processID, proc)
    else:
        checkpointAndMigrateProcessToNode(processID, proc, ipToSend)


def getProcessID(proc) -> int:
    # *Get process ID from process*
    # pid = subprocess.check_output(['pidof', 'f{proc}'])
    return 0  # pid


def criuDump(proc, command=None) -> bool:
    result = subprocess.check_output(['sudo', 'criu', 'dump', '-t', f'$(pgrep {proc})', '-v4', '-o', 'output.log', '&&', 'echo', 'OK'])
    if result == "OK":
        return True
    raise Exception(f"CRIU Dump Result: '{result}', Expected: OK")


def criuRestore(path, command=None) -> bool:
    result = subprocess.check_output(['sudo', 'criu', 'restore', '-d', '-v4', '-o', 'restore.log', '&&', 'echo', 'OK'])
    if result == "OK":
        return True
    raise Exception(f"CRIU Restore Result: '{result}', Expected: OK")


def sendProcessResultsToUser():
    # os.system("scp .....")
    # os.system("ssh to other node, create flag file. idk how to do this better")
    pass


def handleStates():
    """Main FSM"""
    global selfState
    match selfState["state"]:
        case State.IDLE:  # idle State, should look inside project directory for files to run
            process = waitForProcessCMD()
            if process:
                selfState = State.BUSY
                startProcessThread(process)

        case State.BUSY:
            migrateReceived: bool = waitForMigrateCMD()
            if migrateReceived:
                selfState = State.MIGRATING
                processID = getProcessID()  # If complete, send output logs or finished process results back to user
            elif process.isComplete():
                selfState = State.IDLE
                sendProcessResultsToUser()

        case State.MIGRATING:
            migrateProcessToAvaliableNode(processID, process)
            # if migration command is manual, then keep the node in idle, else send to shutdown state
            if isManualCMD:
                selfState = State.IDLE
            else:
                selfState = "shutdown"
        case "shutdown":
            # Node will shut down eventually with loss of power, but potentially leaving the option to return to
            # Idle state if power does return and node somehow still can operate
            if not isLossOfPower():
                selfState = State.IDLE
    return selfState


def main():
    # state["ip"] = socket.gethostbyname(socket.gethostname())
    try:
        broadcaster = BroadcastSender()  # Start broadcast sender and receiver threads
        broadcaster.start()
        receiver = BroadcastReceiver()
        receiver.start()

        while True:
            # handleStates()  # Main FSM
            pass
    except KeyboardInterrupt:  # Handle keyboard interrupts
        broadcaster.stop()
        broadcaster.join()
        receiver.stop()
        receiver.join()
        print("Exiting...")
        sys.exit(0)

    except Exception as e:  # Handle any exceptions
        broadcaster.stop()
        broadcaster.join()
        receiver.stop()
        receiver.join()
        print(e)
        print("Exiting...")
        sys.exit(1)


class BroadcastSender(threading.Thread):
    def __init__(self, address='255.255.255.255', port=12345):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.send_delay = 0.2
        self.baddress = address
        self.port = port
        self._running = True
        super().__init__()

    def run(self):
        global selfState, EXIT
        while self._running:
            ran = random.randrange(139, 143, 1)
            selfState["ip"] = f"192.168.137.{ran}"  # this is temporary for testing. will be replaced with actual ip when we have a network-------------
            self.socket.sendto(pickle.dumps(selfState), (self.baddress, self.port))
            time.sleep(self.send_delay)
            print(f"broadcasting state {selfState['ip']}")
        print("Closing Socket!")
        self.socket.close()
        print("Stopped Broadcast!")

    def stop(self):
        self._running = False


class BroadcastReceiver(threading.Thread):
    """This class is used to listen for incoming broadcast status packets from the nodes so each node can know the status of the other nodes"""

    def __init__(self):
        self._running = True
        self.listenPort = 12345
        self.sockSize = 512
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Create a UDP socket
        self.sock.settimeout(1)  # Set a timeout so the socket doesn't block indefinitely when trying to receive data
        self.sock.bind(('', self.listenPort))  # Listen on all interfaces on port 12345 for broadcast packets
        self.timeout_reset_counter = 8  # every 8 timeouts, clear the uniqueOtherNodeStatuses dictionary to remove old nodes
        super().__init__()

    def run(self):
        global uniqueOtherNodeStatuses

        while self._running:
            try:
                packet = pickle.loads(self.sock.recvfrom(self.sockSize)[0])
                # TODO: Ignore packets that come from self ip address. This does not work yet because the broadcast ip is randomly generated for testing ---------------
                uniqueOtherNodeStatuses[packet["ip"]] = packet
                # print(list(uniqueOtherNodeStatuses.values())) # Print the packet for debugging purposes
            except socket.timeout:
                if self.timeout_reset_counter-1 == 0:
                    uniqueOtherNodeStatuses = {}  # If we don't receive any data within the timeout period, clear the uniqueOtherNodeStatuses dictionary
                    self.timeout_reset_counter = 8
            except Exception as e:  # If we receive any other exception, just print it and keep listening
                print(e)

    def stop(self):
        self._running = False


if __name__ == '__main__':  # if we are running in the main context
    main()  # run the main function. python is weird and this is how you do it
