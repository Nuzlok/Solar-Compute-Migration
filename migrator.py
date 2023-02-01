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

from gpiozero import MCP3008

# https://gpiozero.readthedocs.io/en/stable/api_input.html#mcp3008


class State(Enum):
    IDLE = auto()			# Node is idle and ready to accept
    BUSY = auto()			# Node is busy with processes and cannot accept processes
    MIGRATING = auto()  	# Node is migrating to another and cannot accept processes
    SHUTDOWN = auto()		# Node is shutting down and cannot accept processes

    def __str__(self):
        if self == self.IDLE:
            return "idle"
        if self == self.BUSY:
            return "busy"
        if self == self.MIGRATING:
            return "migrating"
        if self == self.SHUTDOWN:
            return "shutdown"


selfState = {"ip": "", "status": "online", "state": State.IDLE, "current": 0, "voltage": 0, "manual": False, "migrate_cmd": False, "reboot_cmd": False, "shutdown_cmd": False, }
uniqueOtherNodeStatuses = {}
nodeIPaddrs = []
processID = ""
isManualCMD = ""
EXIT = False


class Process:
    """
    Process class.
    Contains all the information about a process.
    This class is used to control the process.
    """

    def __init__(self, procName: str, IP: IPv4Address) -> None:
        self.procName = procName
        self.aliasIP = IP
        pass

    def __str__(self) -> str:
        return f"Process: <Name:{self.procName}, PID:{self.getPID()}, IP:{self.aliasIP}, State:{self.getProcessState()}>"

    def getPID(self) -> int:
        return 0

    def getProcessName(self) -> str:
        return ""

    def getProcessState(self) -> str:
        return ""

    def getAliasedIP(self) -> str:
        return IPv4Address("0.0.0.0")

    def terminate(self):
        pass

    def start(self):
        pass


class ADC:
    """
    `Note: This Class is not yet calibrated and should only be run on a raspberry pi`\n
    Read voltage and current from GPIO pins.
    This class provides function to calculate the power.
    """

    def __init__(self):
        # TODO: calibrate voltage and current values, and scaling factor
        self.voltage = MCP3008(channel=2, differential=False, max_voltage=3.3)
        self.current = MCP3008(channel=1, differential=True, max_voltage=3.3)  # differential on channel 1 and 0, might need to change to pin 0 if output is inverted

    def readPower(self) -> tuple:
        if not os.uname().machine.startswith("arm"):
            raise Exception("ADC can only be run on a raspberry pi")
        return self.voltage.value, self.current.value


def isLossOfPower(CThreshold=0.5, VThreshold=0.5) -> bool:
    """
    Decide when node is losing power by reading 
    voltage and current from GPIO pins
    `Note: This function is not yet calibrated`
    """
    voltage, current = ADC.readPower()
    return (voltage < VThreshold or current < CThreshold)


def startProcessThread(proc: Process) -> bool:
    """
    Start the received process in a new thread
    return true if successful
    """
    return False


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
    if selfState["manual"] and selfState["migrate_cmd"] == True:
        selfState["migrate_cmd"] = False
        return True
    return False


def sendFinishTransferFlag(username="pi", ip="1", password="pi", path=""):
    result = subprocess.run(["ssh", "-t", f"{username}@{ip}", "-p", f"{password}", f"touch {path}; exit"], stdout=subprocess.PIPE)
    if result.returncode == 0:
        print("File updated successfully")
    else:
        print("Failed to update file")


def pollNodeforState(address: IPv4Address) -> str:
    """
    Poll node at given address to get state.
    Used to confirm node status before migrating process to it.
    """
    # *TCP address for Node State*
    statefromNode = State.IDLE
    return statefromNode


def waitForProcess(directory=None) -> Process:
    # Check specified directory for files of a process with finish flag
    # if files are found with the flag, create a process object and return it
    # else return None

    # *Check directory for files of a process*
    return None


def checkpointandSaveProcessToDisk(processID: int, proc: Process):
    """Handle case of no available nodes, checkpoint process to current working directory"""
    # *Run bash Script to checkpoint node and Save to receiving directory on current node*
    # *That way, on startup any files inside the directory will immediately be restored from
    # Checkpoint and resumed on system*
    pass


def checkpointAndMigrateProcessToNode(processID: int, proc: Process):
    # Handle checkpointing and migration
    # *Run bash Script to checkpoint node and SCP to address in specific directory*
    # *Delete process and supporting files on current node*

    # 1. Checkpoint process
    # 2. remove IP alias from current node
    # 3. rsync process directory to receiving node
    # 3. Send finish flag to node
    # 4. Delete process and supporting files on current node

    if checkpointandSaveProcessToDisk(processID, proc) == False:
        raise Exception("Failed to checkpoint process")
    if handleIPaliasing(proc.getAliasedIP(), False) == False:
        raise Exception("Failed to remove IP alias from current node")


def handleIPaliasing(address: IPv4Address, add: bool) -> bool:
    # *Run bash script to add IP alias to current node*
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
        checkpointandSaveProcessToDisk(processID, proc)
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
            process = waitForProcess()
            if process is not None:
                if startProcessThread(process):
                    selfState = State.BUSY
                else:
                    raise Exception("Failed to start process thread. Process not started.")

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
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow the socket to be reused
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
