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
from typing import List

from gpiozero import MCP3008

# https://gpiozero.readthedocs.io/en/stable/api_input.html#mcp3008


class NodeState(Enum):
    IDLE = auto()			# Node is idle and ready to accept
    BUSY = auto()			# Node is busy with processes and cannot accept processes
    MIGRATING = auto()  	# Node is migrating to another and cannot accept processes
    SHUTDOWN = auto()		# Node is shutting down and cannot accept processes

    def __str__(self):
        return self.name


class ProcState(Enum):
    RUNNING = auto()  # Process is running
    WAITING = auto()  # Process is waiting to be started
    TERMINATED = auto()  # Process is terminated forcefully
    COMPLETED = auto()  # Process is completed successfully
    ERROR = auto()  # Process is terminated due to an error
    NONE = auto()  # THere is no process

    def __str__(self):
        return self.name


selfState = {"ip": "", "status": "online", "state": NodeState.IDLE, "current": 0, "voltage": 0, "manual": False, "migrate_cmd": False, "reboot_cmd": False, "shutdown_cmd": False, }
uniqueOtherNodeStatuses = {}
nodeIPaddrs = []
processID = ""
isManualCMD = ""
EXIT = False
DIRECTORY = "/home/pi/ReceivedProcesses/"


class Process:
    """
    Process class.
    Contains all the information about a process and provides functions to start, stop, and terminate the process.
    """

    def __init__(self, name: str):
        print("TODO: process init not complete yet")

        self.procName = name
        self.location = DIRECTORY + name
        self.procState = ProcState.NONE
        self.pid = None
        # self.aliasIP = getAvailableIP()  # TODO: get an available IP address for the process (check list of used IPs and invert that list)

    def __str__(self) -> str:
        return f"Process: <Name:{self.procName}, PID:{self.getPID()}, IP:{self.aliasIP}, State:{self.getProcessState()}>"

    def getPID(self) -> int | None:
        """Get the PID of the process. returns None if process is not running"""
        # return self.pid
        return None

    def getProcessName(self) -> str:
        """Get the name of the process. This is the name of the executable, not the PID or anything else"""
        return self.procName

    def getProcessState(self) -> ProcState:
        """Get the state of the process (running, stopped, etc)"""
        return ProcState.NONE

    def getAliasedIP(self) -> IPv4Address:
        """Get the IP address of the process"""
        return IPv4Address("0.0.0.0")

    def getDirectory(self) -> str | None:
        """Get the directory of the process. returns None if process does not have a directory"""
        return self.location

    def terminate(self) -> bool:
        """Terminate the process. returns True if successful"""
        return True

    def start(self) -> bool:
        """
        Start the received process in a new thread
        return true if successful
        """
        # self.pid
        # print(f"Starting process: {self.procName} on {self.aliasIP}")
        return False


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


def NetworkScan() -> List[IPv4Address]:
    """
    perform a ping scan for available nodes on the network
    return: a list of IPv4Addresses of the available nodes
    """
    selfIP = socket.gethostbyname(socket.gethostname())
    gateway, cidrConf = subprocess.run(['ip', 'route'], capture_output=True, text=True).stdout.splitlines()  # get the network configuration of the node
    gateIP = gateway.split(' ')[2]  # get the gateway ip of the current network from the network configuration
    cidrIP = cidrConf.split(' ')[0]  # get the full cidr of the current network from the network configuration

    nodeIPs = []
    lines = subprocess.run(['sudo', 'arp-scan', cidrIP, '-x', '-q', '-g'], capture_output=True, text=True).stdout.splitlines()
    for line in lines:  # for every found node in the network
        nodeIPs.append(IPv4Address(line.split('\t')[0]))  # add the ip of that node to the list

    nodeIPs = [x for x in nodeIPs if x not in [selfIP, gateIP]]  # removing own ip and gateway ip from the list
    return nodeIPs


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


def waitForProcReceive() -> Process | None:
    """
    Check specified directory for files of a process with finish flag.
    if files are found with the flag, create a process object and return it.
    """
    global DIRECTORY
    received = next(iter(os.listdir(DIRECTORY)), None)  # check if there are any files in the directory
    if received == None:
        return None
    if os.path.exists(os.path.join(DIRECTORY + received, "FLAG.TXT")) == False:
        return None
    return Process(received)


def checkpointandSaveProcessToDisk(proc: Process):
    """Handle case of no available nodes, checkpoint process to current working directory"""
    # *Run bash Script to checkpoint node and Save to receiving directory on current node*
    # *That way, on startup any files inside the directory will immediately be restored from
    # Checkpoint and resumed on system*
    pass


def checkpointAndMigrateProcessToNode(proc: Process, receivingIP: IPv4Address):
    """
    Handle checkpointing and migration
    1. Checkpoint process
    2. confirm node is available and ready to receive process
    3. remove IP alias from current node
    4. rsync process directory to receiving node
    5. Send finish flag to node
    6. Delete process and supporting files on current node
    """

    if checkpointandSaveProcessToDisk(proc) == False:
        raise Exception("Failed to checkpoint process")

    if pollNodeforState(receivingIP) != NodeState.IDLE:
        raise Exception("Receiving node is not ready to receive process")

    if handleIPaliasing(proc.getAliasedIP(), False) == False:
        raise Exception("Failed to remove IP alias from current node")

    if rsyncProcessToNode(proc, receivingIP) == False:
        raise Exception("Failed to rsync process to receiving node")

    if sendFinishTransferFlag(receivingIP) == False:
        raise Exception("Failed to send finish flag to receiving node")

    if deleteProcessFromDisk(proc) == False:
        raise Exception("Failed to delete process from disk")


def deleteProcessFromDisk(proc: Process):
    directory = proc.getDirectory()
    if os.system(f"rm -rf {directory}") != 0:
        return False
    return True


def rsyncProcessToNode(proc: Process, receivingIP: IPv4Address, username="pi"):
    """rsync process to receiving node"""
    sendDir = proc.getDirectory()
    os.system(f"rsync -avz {sendDir} {username}@{receivingIP}:{DIRECTORY}")
    return True


def addIPalias(address: IPv4Address) -> bool:
    """add IP alias to current node"""
    return True
    return os.system(f"ip addr add {address}/24 dev eth0")


def remIPalias(address: IPv4Address) -> bool:
    # Run bash script to remove the IP alias from the node
    return True
    return os.system(f"ip addr del {address}/24 dev eth0")


def migrateProcessToAvaliableNode(processID: int, proc: Process):
    global selfState
    ipToSend = None
    for address in nodeIPaddrs:
        selfState = pollNodeforState(address)
        if selfState == NodeState.IDLE:
            if ipToSend == None:
                ipToSend = address
            else:
                # * Possible comparison for other factors like time, weather, etc.*
                ipToSend = address
    if ipToSend == None:
        checkpointandSaveProcessToDisk(processID, proc)
    else:
        checkpointAndMigrateProcessToNode(processID, proc, ipToSend)


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
        case NodeState.IDLE:  # idle State, should look inside project directory for files to run
            process = waitForProcReceive()
            if process is not None:
                if startProcessThread(process):
                    selfState = NodeState.BUSY
                else:
                    raise Exception("Failed to start process thread. Process not started.")

        case NodeState.BUSY:
            migrateReceived: bool = waitForMigrateCMD()
            if migrateReceived:
                selfState = NodeState.MIGRATING
                processID = getProcessID()  # If complete, send output logs or finished process results back to user
            elif process.isComplete():
                selfState = NodeState.IDLE
                sendProcessResultsToUser()

        case NodeState.MIGRATING:
            migrateProcessToAvaliableNode(processID, process)
            # if migration command is manual, then keep the node in idle, else send to shutdown state
            if isManualCMD:
                selfState = NodeState.IDLE
            else:
                selfState = "shutdown"
        case "shutdown":
            # Node will shut down eventually with loss of power, but potentially leaving the option to return to
            # Idle state if power does return and node somehow still can operate
            if not isLossOfPower():
                selfState = NodeState.IDLE
    return selfState


def main():
    raise Exception("Main function not implemented. Do not run this yet.")
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
        print("Exiting...")
        broadcaster.stop()
        broadcaster.join()
        receiver.stop()
        receiver.join()

        sys.exit(0)

    except Exception as e:  # Handle any exceptions
        print(e, "\nExiting...")
        broadcaster.stop()
        receiver.stop()
        broadcaster.join()
        receiver.join()

        sys.exit(1)  # Exit with error code 1


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
