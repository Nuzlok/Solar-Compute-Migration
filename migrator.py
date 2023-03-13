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

import pexpect

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
    DUMPED = auto()      # Process is dumped
    COMPLETED = auto()   # Process is completed successfully
    ERROR = auto()		 # Process is terminated due to an error
    NONE = auto()		 # There is no process

    def __str__(self):
        return self.name


selfState = {"ip": "", "status": "online", "state": NodeState.IDLE, "current": 0, "voltage": 0, "manual": False, "migrate_cmd": False, "reboot_cmd": False, "shutdown_cmd": False, aliasList: None}
uniqueOtherNodeStatuses = {}  # set of unique statuses from other nodes (all nodes except this one). indexed by IP address
DIRECTORY = "/home/pi/ReceivedProcesses/"  # directory to store processes that are received from other nodes


class Process:
    """
    Contains all the information about a process and provides functions to start, stop, and terminate the process.
    """

    def __init__(self, name: str, location=None, aliasIP=None):
        self.procState = ProcessState.NONE
        self.procName = name
        self.location = location
        self.aliasIP = aliasIP  # getAvailableIP()  # TODO: get an available IP address for the process (check list of used IPs and invert that list)
        self.pid = None

    def __str__(self) -> str:
        return f"Process: <Name:{self.procName}, Location:{self.location}, PID:{self.pid}, IP:{self.aliasIP}, State:{self.procState}>"

    def getProcessName(self) -> str:
        """Get the name of the process. This is the name of the executable, not the PID or anything else"""
        return self.procName

    def getDirectory(self) -> str:
        """Get the directory of the process. returns None if process does not have a directory"""
        return self.location

    def terminate(self) -> bool:
        """Terminate the process. returns True if successful"""
        if os.system(f"sudo kill -9 {self.pid}") == 0:
            self.procState = ProcessState.TERMINATED
            return True
        return False

    def start(self) -> bool:
        """ Check if the process is a new process or a dumped process. If it is a new process, run it. If it is a dumped process, restore it. """
        if os.path.exists(f"{self.location}/dump.log"):
            # print("restoring process")
            return self.restore()
        else:
            # print("running new process")
            return self.run()

    def run(self, command=None) -> bool:
        """Start a new process. returns True if successful"""
        os.chdir('/home/pi/videoboard')
        os.system("setsid nohup sudo python3 /home/pi/videoboard/vidboardmain.py --bind_ip 192.168.137.3 </dev/null &>/dev/null &")
        os.system("disown")
        time.sleep(2)  # Wait for the process to start before getting the PID
        self.pid = subprocess.check_output(['pgrep', '-f', 'vidboardmain.py']).decode().strip()  # Get the PID of the process
        print(f"Starting {self}")
        os.chdir('/home/pi')
        return self.pid != ""

        # self.pid = os.spawnlp(os.P_NOWAIT, 'python3', 'python3', '/home/pi/videoboard/vidboardmain.py', f'--bind_ip={self.aliasIP}')  # Get the PID of the process
        # if self.pid != "":  # If the PID is not empty
        #     self.procState = ProcessState.RUNNING
        #     print(f"Created {self}")  # self has a __str__ method that prints the process name and PID
        #     return True
        # return False

    def restore(self, log_level="-vvvv", log_file="restore.log", shell=True, tcp=True) -> bool:
        """ Start an existing dumped process. return True if successful. """

        IPalias(f"{self.aliasIP}", True)
        os.chdir(f'{self.location}')
        os.system(f"cd {self.location}")
        command = f"unshare -p -m --fork --mount-proc criu restore {log_level} -o {log_file}"

        command += " --shell-job" if shell else ""
        command += " --tcp-established" if tcp else ""
        if not os.system(command) == 0:  # 0 means success
            return False

        result = subprocess.run(['ps', 'ax'], stdout=subprocess.PIPE).stdout
        result = subprocess.run(['grep', 'vidboardmain.py'], input=result, stdout=subprocess.PIPE).stdout.decode().split()[0]  # TODO: use the arbitrary process name instead of hardcoding it
        self.pid = result

        if self.pid != "":  # If the PID is not empty
            print(f"Restoring {self}")  # self has a __str__ method that prints the process name and PID
            self.procState = ProcessState.RUNNING
            return True
        return False

    def dump(self, log_level="-vvvv", log_file="output.log", shell=True, tcp=True) -> bool:
        """ Dump the process using CRIU. Accepts a command to run after the dump is complete. returns True if successful. """
        os.system("rm -rf core* fs* ids* invent* mm-* pagemap* pages* pstree* seccomp* stats* tcp* timens* tty* files* fdinfo*")
        print(f"Dumping {self}")

        # command = ['sudo', 'dump', log_level, '-o', log_file, '-t', f'{self.pid}']
        command = ['sudo', 'criu', 'dump', log_level, '-o', log_file, '-t', f'{self.pid}']
        command += ['--shell-job'] if shell else []
        command += ['--tcp-established'] if tcp else []

        print(f"{command=}")
        result = subprocess.run(['ps', 'ax'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        lines = result.stdout.decode().split('\n')  # TODO: use the arbitrary process name instead of hardcoding it, also use grep instead of this (try os.popen('ps ax | grep {process_name}'))
        matching_lines = [line for line in lines if "vidboardmain.py" in line]
        print(f'{matching_lines=}')
        self.pid = matching_lines[-1].split()[0]
        print(f'{self.pid=}')
        os.chdir('/home/pi/videoboard')
        os.system(f"sudo criu dump -vvvv -o dump.log -t {self.pid} --shell-job --tcp-established --ghost-limit 100q000000 && echo OK")
        time.sleep(0.1)
        os.chdir('/home/pi')
        self.procState = ProcessState.DUMPED
        return True

        # os.spawnvp(os.P_WAIT, 'criu', command)

        # if os.system(f"pgrep -f {self.procName}") != 0:
        # if os.system(f"pgrep -f vidboardmain.py") != 0:
        #     return False
        # self.procState = ProcessState.DUMPED
        # return True

    def deleteFromDisk(self) -> bool:
        # return os.system(f"rm -rf {self.getDirectory()}") == 0
        return os.system(f"rm -rf /home/pi/videoboard") == 0


def isLossOfPower(vThresh=6.1, cThresh=0.5, vScale=10, cScale=1) -> bool:
    """ Decide when node is losing power by comparing the voltage and current to a threshold. """

    vol, curr = voltage.value * vScale, current.value / cScale

    # TODO: Set vTresh to expected panel threshold voltage (Currently at an estimated value 4.8 + 1.3)

    return vol < vThresh


def getMigrateCMD(forceMigrate=False) -> bool:
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


def sendFinishFlag(path: str, ip: IPv4Address, username="pi", password="pi") -> None:
    """ 
    Send a flag to the destination node to indicate that the file transfer is complete.
    without this flag, the destination node will not know if an error occurred during the transfer.
    """

    ssh_cmd = f'sudo scp /home/pi/flag.txt {username}@{ip}:{path}/'
    child = pexpect.spawn(ssh_cmd, timeout=30)  # spawnu for Python 3
    child.expect([f'{username}@{ip}\'s password: '])
    child.sendline(f'{password}')
    child.expect(pexpect.EOF)
    child.close()
    return child.exitstatus


def getNewProcess() -> Process:
    """
    Check specified directory for files of a process with finish flag.
    if files are found with the flag, create a process object and return it.
    """
    # global DIRECTORY # Not sure if I need this or not.

    directory = "/home/pi/videoboard"  # TODO: change this to the directory that the process files are stored in using the commented out code below

    if os.path.exists(f'{directory}/flag.txt') == False:  # dont need to look for the folder, we can check for the flag directly
        return None
    print("Flag File Found, creating process")
    return Process("videoboard", location=directory, aliasIP=IPv4Address("192.168.137.3"))  # TODO: change the IP address to a new IP for the process

    # # received is the name of the directory that contains the process files
    # received = next(iter(os.listdir(DIRECTORY)), None) # this will return the first item in the list, or None if the list is empty
    # if received == None: return None
    # if os.path.exists(os.path.join(DIRECTORY + received, "FLAG.TXT")) == False: return None
    # return Process(received)


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

    print("Beginning checkpoint and migration process")

    if proc.dump() == False:
        raise Exception("Failed to checkpoint process, dumping failed")
    print("Process dumped successfully")

    # if confirmNodeAvailable(receivingIP) == False:
    #     raise Exception("Receiving node is not available, node did not update its state")
    # print("Receiving node is available")

    if IPalias(proc.aliasIP, False) == False:
        raise Exception("Failed to remove IP alias from current node, new node will not be able to run process")
    print("IP alias removed from current node")

    # if rsyncProcessToNode(proc, receivingIP) == False:
    #     raise Exception("Failed to rsync process to receiving node, process may be incomplete")
    # print("Process rsynced to receiving node")

    # if sendFinishFlag(ip=receivingIP, path=proc.procName) == False:
    #     raise Exception("Failed to send finish flag to receiving node, process may be incomplete")
    # print("Finish flag sent to receiving node")

    # if proc.deleteFromDisk() == False:
    #     raise Exception("Failed to delete process from disk, process might accidentally be run again")
    # print("Process deleted from disk")


def rsyncProcessToNode(proc: Process, ip: IPv4Address, password="pi", username="pi"):
    """rsync dumped files to receiving node"""
    # spawn rsync -avz /home/pi/{proc.getDirectory()} pi@{ip}:{DIRECTORY}

    ssh_cmd = f'sudo scp -r /home/pi/{proc.getDirectory()} {username}@{ip}:/home/pi/'
    child = pexpect.spawn(ssh_cmd, timeout=30)
    child.expect([f'{username}@{ip}\'s password: '])
    child.sendline(f'{password}')
    child.expect(pexpect.EOF)
    child.close()
    return child.exitstatus

# def IPalias(address: IPv4Address, add: bool) -> bool:
#     """Handle IP alias to current node. set add to true to add alias, and vice versa"""
#     global selfState
#     if add:
#         if selfState["ip_alias"] == None:
#             selfState["ip_alias"] = [address]
#         else:
#             selfState["ip_alias"].append(address)
#         return os.system(f"ip addr add {address}/24 dev eth0") == 0
#     else:
#         selfState["ip_alias"].remove(address)
#         return os.system(f"ip addr del {address}/24 dev eth0") == 0


def IPalias(address: IPv4Address, add: bool) -> bool:
    """Handle IP alias to current node. set add to true to add alias, and vice versa"""
    if add:
        return os.system(f"ip addr add {address}/24 dev eth0") == 0
    return os.system(f"ip addr del {address}/24 dev eth0") == 0


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
    print(f"{(5*voltage.value) :=.5f}, state={selfState['state']}, Press Ctrl-C to exit")
    time.sleep(0.05)  # make sure it doesnt hog the CPU

    # ------------------ Change State ------------------
    if isLossOfPower(vThresh=4.1) or getMigrateCMD():
        selfState["state"] = NodeState.MIGRATING
    elif isLossOfPower(vThresh=4.0):
        selfState["state"] = NodeState.SHUTDOWN

    # ------------------ Execute State ------------------
    if selfState["state"] == NodeState.IDLE:
        process = getNewProcess()
        if process:
            IPalias(process.aliasIP, True)
            if process.start() == False:
                raise RuntimeError("Failed to start process thread. Process not started.")
            selfState["state"] = NodeState.BUSY
        #   if process.restore() == False:
        #       raise RuntimeError("Failed to start process thread. Process not started.")

    if selfState["state"] == NodeState.BUSY:
        if process.procState == ProcessState.COMPLETED:
            # sendProcessResultsToUser() # TODO: if we want to send the results back to the user, we can do that here
            selfState["state"] = NodeState.IDLE

    if selfState["state"] == NodeState.MIGRATING:
        checkpointAndMigrateProcessToNode(process, IPv4Address("192.168.137.140"))  # TODO: remove hardcoded IP and replace with findAvailableNode()
        selfState["state"] = NodeState.SHUTDOWN

    if selfState["state"] == NodeState.SHUTDOWN:
        raise Exception("Shutdown command received")

    return process


def main():
    global voltage, current, selfState

    # get the ip address of the current host and store it in the selfState dictionary
    selfState["ip"] = socket.gethostbyname(socket.gethostname())

    try:
        broadcaster = BroadcastSender()  # Start broadcast sender and receiver threads
        broadcaster.start()
        receiver = BroadcastReceiver()
        receiver.start()
        process = None
        # https://gpiozero.readthedocs.io/en/stable/api_input.html#mcp3008
        voltage = MCP3008(channel=2, differential=False, max_voltage=5)  # single ended on channel 2
        current = MCP3008(channel=1, differential=True, max_voltage=5)  # differential on channel 1 and 0, might need to change to pin 0 if output is inverted
        print(f"reading voltage from pin 2, current from pin 0-1")
        while True:
            process = MainFSM(process)  # Main FSM
    except (KeyboardInterrupt, Exception) as e:
        broadcaster.stop()
        broadcaster.join()
        receiver.stop()
        receiver.join()
        # for alias in selfState["ip_alias"]:
        #     IPalias(alias, False)
        print("Exiting...")
        if not isinstance(e, KeyboardInterrupt):
            raise e


class BroadcastSender(threading.Thread):
    """ 
    This class is used to create a thread that sends broadcast packets to other nodes. 
    The packets contain the node's current state and IP address.
    """

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
            # ran = random.randrange(139, 143, 1)
            # selfState["ip"] = f"192.168.137.{ran}"  # this is temporary for testing. will be replaced with actual ip when we have a network-------------
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
    main()
