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

try:
    import RPi.GPIO  # ensure pin factory is set to RPi.GPIO
    import spidev  # only for gpio pins on raspberry pi
    from gpiozero import MCP3008
except ImportError as e:
    print("Make sure gpiozero, spidev, and RPi.GPIO are installed")
    raise Exception("Make sure gpiozero, spidev, and RPi.GPIO are installed")


class NodeState(Enum):
    IDLE = auto()			# Node is idle and ready to accept
    BUSY = auto()			# Node is busy with processes and cannot accept processes
    MIGRATING = auto()  	# Node is migrating to another and cannot accept processes
    SHUTDOWN = auto()		# Node is shutting down and cannot accept processes

    def __str__(self):
        return self.name


class ProcessState(Enum):
    RUNNING = auto()  # Process is running
    WAITING = auto()  # Process is waiting to be started
    TERMINATED = auto()  # Process is terminated forcefully
    COMPLETED = auto()  # Process is completed successfully
    ERROR = auto()		# Process is terminated due to an error
    NONE = auto()		# There is no process

    def __str__(self):
        return self.name


selfState = {"ip": "", "status": "online", "state": NodeState.IDLE, "current": 0, "voltage": 0, "manual": False, "migrate_cmd": False, "reboot_cmd": False, "shutdown_cmd": False, }
uniqueOtherNodeStatuses = {}  # set of unique statuses from other nodes (all nodes except this one). indexed by IP address
DIRECTORY = "/home/pi/ReceivedProcesses/"  # directory to store processes that are received from other nodes


class Process:
    """
    Process class.
    Contains all the information about a process and provides functions to start, stop, and terminate the process.
    """

    def __init__(self, name: str):
        print("TODO: Process __init__ not implemented yet.")
        self.procState = ProcessState.NONE

    def create(self, name: str, location: str, aliasIP: IPv4Address, pid: int):
        print("TODO: Process create() not implemented yet.")
        self.procName = name
        self.location = location
        self.aliasIP = aliasIP  # getAvailableIP()  # TODO: get an available IP address for the process (check list of used IPs and invert that list)
        self.pid = pid

    def __str__(self) -> str:
        return f"Process: <Name:{self.procName}, PID:{self.getPID()}, IP:{self.aliasIP}, State:{self.procState}>"

    def getProcessName(self) -> str:
        """Get the name of the process. This is the name of the executable, not the PID or anything else"""
        return self.procName

    def getAliasedIP(self) -> IPv4Address:
        """Get the aliased IP address of the process"""
        return self.aliasIP

    def getDirectory(self) -> str:
        """Get the directory of the process. returns None if process does not have a directory"""
        return self.location

    def terminate(self) -> bool:
        """Terminate the process. returns True if successful"""
        return True

    def run(self) -> bool:
        """
        Start the received process in a new thread
        return true if successful
        """
        # self.pid
        # print(f"Starting process: {self.procName} on {self.aliasIP}")
        return True

    def dump(self, command=None, dumpToDisk=False) -> bool:
        """ Dump the process using CRIU. Accepts a command to run after the dump is complete. returns True if successful"""

        result = subprocess.check_output(['sudo', 'criu', 'dump', '-t', f'{self.pid}', '-v4', '-o', 'output.log', '&&', 'echo', 'OK'])
        if result != "OK":
            raise Exception(f"CRIU Dump Result: '{result}', Expected: OK")
        if dumpToDisk:
            os.system(f"mv -R ./{self.location} {DIRECTORY}{self.location}")
            result = os.system(f"touch {DIRECTORY}{self.location}/FINISH.TXT")
            if result != 0:
                print("Finish Flag not copied. dump incomplete")
                raise Exception("Finish Flag not copied. dump incomplete")

    def deleteFromDisk(self):
        if os.system(f"rm -rf {self.getDirectory()}") != 0:
            return False
        return True


# https://gpiozero.readthedocs.io/en/stable/api_input.html#mcp3008
voltage = MCP3008(channel=2, differential=False, max_voltage=5)  # single ended on channel 2
current = MCP3008(channel=1, differential=True, max_voltage=5)  # differential on channel 1 and 0, might need to change to pin 0 if output is inverted


def isLossOfPower(vThresh=4.8, cThresh=0.5, vScale=5, cScale=1) -> bool:
    """ Decide when node is losing power by comparing the voltage and current to a threshold. """
    global voltage, current

    vol, curr = voltage.value * vScale, current.value * cScale

    return vol < vThresh  # just check voltage for now, current is tested
    # return (vol < vThresh or curr < cThresh)


def awaitMigrateSignal(forceMigrate=False) -> bool:
    """
    Handle migrate command. Returns true when the process should be migrated.
    Migration is triggered by a loss of power or a manual migate command through the HMI.
    forceMigrate parameter is there for testing purposes, and in case there is a future need to force a migration.
    """
    global selfState
    if isLossOfPower() or forceMigrate:
        return True
    if selfState["migrate_cmd"] == True:
        selfState["migrate_cmd"] = False
        return True
    return False


def sendFinishTransferFlag(path: str, ip: IPv4Address, username="pi", password="pi") -> None:
    """ 
    Send a flag to the destination node to indicate that the file transfer is complete.
    without this flag, the destination node will not know if an error occurred during the transfer.
    """
    result = subprocess.run(["ssh", "-t", f"{username}@{ip}", "-p", f"{password}", f"touch {path}/FLAG.TXT; exit"], stdout=subprocess.PIPE)
    if result.returncode != 0:
        return print("Failed to update file")
    print("File updated successfully")


def waitForProcReceive() -> Process:
    """
    Check specified directory for files of a process with finish flag.
    if files are found with the flag, create a process object and return it.
    """

    return Process("")  # For testing purposes

    # global DIRECTORY # Not sure if I need this or not.
    received = next(iter(os.listdir(DIRECTORY)), None)  # check if there are any files in the directory
    if received == None:
        return None
    if os.path.exists(os.path.join(DIRECTORY + received, "FLAG.TXT")) == False:
        return None
    return Process(received)


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

    if proc.dump() == False:
        raise Exception("Failed to checkpoint process")

    if confirmNodeAvailable(receivingIP) != NodeState.IDLE:
        raise Exception("Receiving node is not ready to receive process")

    if IPalias(proc.getAliasedIP(), False) == False:
        raise Exception("Failed to remove IP alias from current node")

    if rsyncProcessToNode(proc, receivingIP) == False:
        raise Exception("Failed to rsync process to receiving node")

    if sendFinishTransferFlag(receivingIP) == False:
        raise Exception("Failed to send finish flag to receiving node")

    if proc.deleteFromDisk() == False:
        raise Exception("Failed to delete process from disk")


def criuRestore(path, command=None) -> bool:
    """ Restore the process using CRIU. Accepts a command to run after the restore is complete. returns True if successful"""
    result = subprocess.check_output(['sudo', 'criu', 'restore', '-d', '-v4', '-o', 'restore.log', '&&', 'echo', 'OK'])
    if result != "OK":
        print("CRIU Restore Failed")
        return False
    return True


def rsyncProcessToNode(proc: Process, receivingIP: IPv4Address, password="pi"):
    """rsync dumped files to receiving node"""

    # we use expect to automate the password prompt for scp/rsync so we don't have to type it in manually
    expect_script = f"""
	set timeout 30
	spawn rsync -avz /home/pi/{proc.getDirectory()} pi@{receivingIP}:{DIRECTORY}
	expect "password:"
	send "{password}\r"
	expect eof
	"""
    result = subprocess.run(['expect'], input=expect_script, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')

    if result.returncode != 0:  # If the script failed
        print("File transfer failed")


def IPalias(address: IPv4Address, add: bool) -> bool:
    """Handle IP alias to current node"""
    return True
    if add:
        return os.system(f"ip addr add {address}/24 dev eth0")
    else:
        return os.system(f"ip addr del {address}/24 dev eth0")


def findAvailableNode() -> IPv4Address:
    """Find an available node to migrate to"""
    available = []
    for ip, (packet, _) in uniqueOtherNodeStatuses:  # TODO: Check if this is the correct syntax
        if packet["state"] == NodeState.IDLE:  # found an available node
            available.append(ip)

    # TODO: Possible comparison for other factors like time, weather, etc.. here. For now, just return the first available node

    return available[0] if len(available) > 0 else None


def confirmNodeAvailable(ip: IPv4Address) -> bool:
    """Confirm that the node is available to receive a process by waiting for a new packet from the node"""
    last_time = uniqueOtherNodeStatuses[ip][1]
    while time.time() < last_time + 10:  # wait maximum 10 seconds for a new packet from the node
        if uniqueOtherNodeStatuses[ip][1] > last_time:
            return True
    return False  # timed out


def MainFSM(process: Process):
    global selfState
    print(f"{voltage.value=:.5f}, state={selfState['state']}, Press Ctrl-C to exit")
    time.sleep(0.05)  # make sure it doesnt hog the CPU

    if isLossOfPower(vThresh=4.8):
        selfState["state"] = NodeState.MIGRATING
    elif isLossOfPower(vThresh=4.6):
        selfState["state"] = NodeState.SHUTDOWN
    else:
        selfState["state"] = NodeState.IDLE

    if selfState["state"] == NodeState.IDLE:
        # process = waitForProcReceive()
        # if process:  # if we received a process
        #     if process.run() == False:
        #         raise RuntimeError("Failed to start process thread. Process not started.")
        #     selfState["state"] = NodeState.BUSY

        # elif awaitMigrateSignal():  # if we get a migrate signal while doing nothing, do nothing
        #     selfState["state"] = NodeState.SHUTDOWN
        pass

    if selfState["state"] == NodeState.BUSY:
        # if awaitMigrateSignal():
        #     selfState["state"] = NodeState.MIGRATING
        # elif process.procState == ProcessState.FINISHED:
        #     selfState["state"] = NodeState.IDLE
        #     # sendProcessResultsToUser() # TODO: if we want to send the results to the user, we can do that here
        pass

    if selfState["state"] == NodeState.MIGRATING:
        # checkpointAndMigrateProcessToNode(process)
        # selfState["state"] = NodeState.IDLE
        # # if migration command is manual, then keep the node in idle, else send to shutdown state
        # selfState["state"] = NodeState.IDLE if isManualCMD else NodeState.SHUTDOWN
        pass


def main():
    try:
        broadcaster = BroadcastSender()  # Start broadcast sender and receiver threads
        broadcaster.start()
        receiver = BroadcastReceiver()
        receiver.start()
        process = Process("")
        print(f"reading voltage from pin 2")
        print(f"reading current from pin 0 and 1")
        while True:
            MainFSM(process)  # Main FSM
    except (KeyboardInterrupt, Exception) as e:
        broadcaster.stop()
        broadcaster.join()
        receiver.stop()
        receiver.join()
        print("Exiting...")
        raise e


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
        global selfState
        while self._running:
            ran = random.randrange(139, 143, 1)
            selfState["ip"] = f"192.168.137.{ran}"  # this is temporary for testing. will be replaced with actual ip when we have a network-------------
            self.socket.sendto(pickle.dumps(selfState), (self.baddress, self.port))
            time.sleep(self.send_delay)
            # print(f"broadcasting state {selfState['ip']}")
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
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.settimeout(1)                # Set a timeout so the socket doesn't block indefinitely when trying to receive data
        self.sock.bind(('', self.listenPort))  # Listen on all interfaces on port 12345 for broadcast packets
        self.timeout_reset_counter = 8         # every 8 timeouts, clear the dictionary to remove old nodes
        super().__init__()

    def run(self):
        global uniqueOtherNodeStatuses

        while self._running:
            try:
                packet = pickle.loads(self.sock.recvfrom(self.sockSize)[0])
                if packet["ip"] != selfState["ip"]:                              # If the packet is not from this node
                    uniqueOtherNodeStatuses[packet["ip"]] = packet, time.time()
            except socket.timeout:
                if self.timeout_reset_counter-1 == 0:
                    uniqueOtherNodeStatuses = {}      # If we don't receive anything within a period, clear
                    self.timeout_reset_counter = 8
            except Exception as e:                    # If we receive any exception, just print it and continue
                print(e)

    def stop(self):
        self._running = False


if __name__ == '__main__':  # if we are running in the main context
    main()  # run the main function. python is weird and this is how you do it
