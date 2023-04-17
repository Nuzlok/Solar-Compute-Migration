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
import netifaces
import pexpect
from statistics import mean
import RPi.GPIO  # ensure pin factory is set to RPi.GPIO
import spidev  # only for gpio pins on raspberry pi
from gpiozero import MCP3008, LEDBoard, PWMLED


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

# FIXME some of the state variables are not used. Remove them
selfState = {"ip": "", "status": "online", "state": NodeState.IDLE, "current": 0, "voltage": 0, "manual": False, "migrate_cmd": False, "reboot_cmd": False, "shutdown_cmd": False}
uniqueOtherNodeStatuses = {}  # set of unique statuses from other nodes (all nodes except this one). indexed by IP address
DIRECTORY = "/home/pi/ReceivedProcesses/"  # directory to store processes that are received from other nodes
ADC_Values = [(0,0)] * 5  # Store ADC values to smooth  using a moving average
led_4 = PWMLED(4)  # LED on pin 4
led_17 = PWMLED(17)  # LED on pin 17
led_27 = PWMLED(27)  # LED on pin 27
led_22 = PWMLED(22)  # LED on pin 22

class Process:
    # TODO: convert to a dataclass instead of a normal class. This will make the code more readable and easier to use
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
        if os.path.exists(f"/home/pi/cpflag.txt"):
            print("restoring process")
            os.system("sudo rm -rf /home/pi/cpflag.txt")
            return self.restore()
        else:
            print("running new process")
            os.system("sudo rm /home/pi/startflag.txt")
            return self.run()

    def run(self, command=None) -> bool:
        """Start a new process. returns True if successful"""
        procname = "videoboard"
        execName = "vidboardmain.py"
        os.chdir(f'/home/pi/{procname}')
        os.system(f"setsid nohup sudo python3 /home/pi/{procname}/{execName} --bind_ip 192.168.137.3 </dev/null &>/dev/null &")
        time.sleep(2)  # Wait for the process to start before getting the PID
        self.pid = subprocess.check_output(['pgrep', '-f', f'{execName}']).decode().strip()  # Get the PID of the process
        print(f"Starting {self}")
        os.chdir('/home/pi')
        return self.pid != ""

        # self.pid = os.spawnlp(os.P_NOWAIT, 'python3', 'python3', f'/home/pi/{procname}/{execName}', f'--bind_ip={self.aliasIP}')  # Get the PID of the process
        # if self.pid != "":  # If the PID is not empty
        #     self.procState = ProcessState.RUNNING
        #     print(f"Created {self}")  # self has a __str__ method that prints the process name and PID
        #     return True
        # return False

    def restore(self, log_level="-vvvv", log_file="restore.log", shell=True, tcp=True) -> bool:
        """ Start an existing dumped process. return True if successful. """

        procname = "videoboard"
        execName = "vidboardmain.py"
        IPalias(f"192.168.137.3", True)
        os.chdir(f'/home/pi/{procname}')
        command = f"setsid nohup unshare sudo criu restore -vvvv -o restore.log --shell-job --tcp-established &"
        if not os.system(command) == 0:  # 0 means success
            return False

        # time.sleep(10)
        # result = subprocess.run(['ps', 'ax'], stdout=subprocess.PIPE).stdout
        # result = subprocess.run(['grep', f'{execName}'], input=result, stdout=subprocess.PIPE).stdout.decode().split()[0]  # TODO: use the arbitrary process name instead of hardcoding it
        # self.pid = result
        self.procState = ProcessState.RUNNING
        return True

        # TODO: get the PID of the process after it is restored
        if self.pid != "":  # If the PID is not empty
            print(f"Restoring {self}")  # self has a __str__ method that prints the process name and PID
            self.procState = ProcessState.RUNNING
            return True
        return False

    def dump(self, log_level="-vvvv", log_file="output.log", shell=True, tcp=True) -> bool:
        """ Dump the process using CRIU. Accepts a command to run after the dump is complete. returns True if successful. """
        procname = "videoboard"
        execName = "vidboardmain.py"
        os.chdir(f'/home/pi/{procname}')
        os.system("rm -rf core* fs* ids* invent* mm-* pagemap* pages* pstree* seccomp* stats* tcp* timens* tty* files* fdinfo* nohup.out dump.log restore.log flag.txt")
        print(f"Dumping {self}")

        result = subprocess.run(['ps', 'ax'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        lines = result.stdout.decode().split('\n')  # TODO: use the arbitrary process name instead of hardcoding it, also use grep instead of this (try os.popen('ps ax | grep {process_name}'))
        matching_lines = [line for line in lines if f"{execName}" in line]
        self.pid = matching_lines[-1].split()[0]
        os.chdir(f'/home/pi/{procname}')
        os.system(f"sudo criu dump -vvvv -o dump.log -t {self.pid} --shell-job --tcp-established --ghost-limit 100000000 && echo OK")
        time.sleep(0.1)
        os.chdir('/home/pi')
        os.system(f"sudo rm -rf cpflag.txt {procname}/cpflag.txt /home/pi/cpflag.txt startflag.txt {procname}/startflag.txt /home/pi/startflag.txt")
        self.procState = ProcessState.DUMPED
        return True

        # if os.system(f"pgrep -f {execName}") != 0:
        #     return False
        # self.procState = ProcessState.DUMPED
        # return True

    def deleteFromDisk(self) -> bool:
        # return os.system(f"rm -rf {self.getDirectory()}") == 0
        procname = "videoboard"
        return os.system(f"rm -rf /home/pi/{procname}") == 0


def isLossOfPower(vThresh=12, vScale=55, cScale=1) -> bool:
    """ Decide when node is losing power by comparing the voltage and current to a threshold. """
    # get the rolling average of the last 5 values
    if not useADC:
        return False
    ADC_Values.append((voltage.value * vScale, current.value / cScale))
    ADC_Values.pop(0)
    vol, curr = mean([x[0] for x in ADC_Values]), mean([x[1] for x in ADC_Values])
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
    if os.path.exists("/home/pi/force_migrate.txt"):
        os.system("rm -rf /home/pi/force_migrate.txt")
        return True
    return False


def sendFinishFlag(path: str, ip: IPv4Address, username="pi", password="pi") -> None:
    """ 
    Send a flag to the destination node to indicate that the file transfer is complete.
    without this flag, the destination node will not know if an error occurred during the transfer.
    """

    os.system("touch /home/pi/cpflag.txt")
    ssh_cmd = f'sudo scp /home/pi/cpflag.txt {username}@{ip}:/home/pi/'
    print(f"{ssh_cmd=}")
    child = pexpect.spawn(ssh_cmd, timeout=30)
    child.expect([f"{username}@{ip}'s password: "])
    child.sendline(f'{password}')
    child.expect(pexpect.EOF)
    child.close()
    os.system("sudo rm -rf /home/pi/cpflag.txt /home/pi/startflag.txt")
    return child.exitstatus == 0


def getNewProcess() -> Process:
    """
    Check specified directory for files of a process with finish flag.
    if files are found with the flag, create a process object and return it.
    """
    # global DIRECTORY # Not sure if I need this or not.
    procname = "videoboard"

    directory = f"/home/pi/{procname}"  # TODO: change this to the directory that the process files are stored in using the commented out code below

    if os.path.exists(f'/home/pi/startflag.txt') == False and os.path.exists(f'/home/pi/cpflag.txt') == False:  # dont need to look for the folder, we can check for the flag directly
        return None
    print("Flag File Found, creating process")
    return Process(f"{procname}", location=directory, aliasIP=IPv4Address("192.168.137.3"))  # TODO: change the IP address to a new IP for the process

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
    7. Display message with timing information for each step as a bar graph
    """
    start_time_ms = int(time.time()*1000)
    if proc.dump() == False:
        raise Exception("Failed to checkpoint process, dumping failed")
    print("Process dumped successfully")
    dump_time_ms = int(time.time()*1000)

    # if confirmNodeAvailable(receivingIP) == False:
    #     raise Exception("Receiving node is not responding/available")
    # print(f"Confirmed node at {receivingIP} is available")
    # confirm_time_ms = int(time.time()*1000)

    if IPalias(proc.aliasIP, False) == False:
        raise Exception("Failed to remove IP alias from current node, new node will not be able to run process")
    print("IP alias removed from current node")
    alias_time_ms = int(time.time()*1000)

    if receivingIP == None:
        os.system("touch /home/pi/cpflag.txt")
        return True

    if rsyncProcessToNode(proc, receivingIP) == False:
        raise Exception("Failed to rsync process to receiving node, process may be incomplete")
    print("Process rsynced to receiving node")
    rsync_time_ms = int(time.time()*1000)

    if sendFinishFlag(ip=receivingIP, path=proc.procName) == False:
        raise Exception("Failed to send finish flag to receiving node, process may be incomplete")
    print("Finish flag sent to receiving node")
    flag_time_ms = int(time.time()*1000)

    if proc.deleteFromDisk() == False:  
        raise Exception("Failed to delete process from disk, process might accidentally be run again")
    print("Process deleted from disk")
    delete_time_ms = int(time.time()*1000)

    bar_width = 50

    total_time_ms = delete_time_ms-start_time_ms
    with open("/home/pi/migrate_stats.txt", "w") as f:
        f.write(f"Time: {time.time()}")
        f.write(f"Migration took total of {total_time_ms} ms\n")
        f.write(f"{'Dumping':<15} {dump_time_ms-start_time_ms:2.0f} ms {'-'*int((dump_time_ms-start_time_ms)/total_time_ms*bar_width)}\n")
        f.write(f"{'IP alias (rem)':<15} {alias_time_ms-dump_time_ms:2.0f} ms {'-'*int((alias_time_ms-dump_time_ms)/total_time_ms*bar_width)}\n")
        f.write(f"{'Rsyncing':<15} {rsync_time_ms-alias_time_ms:2.0f} ms {'-'*int((rsync_time_ms-alias_time_ms)/total_time_ms*bar_width)}\n")
        f.write(f"{'Finish flag':<15} {flag_time_ms-rsync_time_ms:2.0f} ms {'-'*int((flag_time_ms-rsync_time_ms)/total_time_ms*bar_width)}\n")
        f.write(f"{'Deleting':<15} {delete_time_ms-flag_time_ms:2.0f} ms {'-'*int((delete_time_ms-flag_time_ms)/total_time_ms*bar_width)}\n")

    proc = None  # remove the process from memory after it has been migrated
    return True


def rsyncProcessToNode(proc: Process, ip: IPv4Address, password="pi", username="pi"):
    """rsync dumped files to receiving node"""
    # spawn rsync -avz /home/pi/{proc.getDirectory()} pi@{ip}:{DIRECTORY}
    procname = "videoboard"

    ssh_cmd = f'sudo scp -r /home/pi/{procname} {username}@{ip}:/home/pi/'
    child = pexpect.spawn(ssh_cmd, timeout=30)
    child.expect([f"{username}@{ip}'s password: "])
    child.sendline(f'{password}')
    child.expect(pexpect.EOF)
    child.close()
    return child.exitstatus == 0

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
    for packet, time in uniqueOtherNodeStatuses.values():
        if packet["state"] == NodeState.IDLE:  # found an available node
            available.append(packet["ip"])

    # TODO: Possible comparison for other factors like time, weather, etc.. here. For now, just return the first available node
    if len(available) > 0:
        return available[0]
    return None


def confirmNodeAvailable(ip: IPv4Address) -> bool:
    """Confirm that the node is available to receive a process by waiting for a new packet from the node"""
    last_time = uniqueOtherNodeStatuses[ip][1]
    while time.time() < last_time + 10:  # wait maximum 10 seconds for a new packet from the node
        if uniqueOtherNodeStatuses[ip][1] > last_time:
            return True
    return False  # timed out


def MainFSM(process: Process):
    global selfState
    time.sleep(0.05)  # make sure it doesnt hog the CPU

    if useADC: 
        print(f"{(55*voltage.value) :=.5f}, state={selfState['state']}, Press Ctrl-C to exit")
    else:
        print(f"ADC READING DISABLED, state={selfState['state']}, Press Ctrl-C to exit")


    # ------------------ Change State ------------------
    if selfState["state"] != NodeState.SHUTDOWN:
        if isLossOfPower() or getMigrateCMD():
            selfState["state"] = NodeState.MIGRATING
        elif isLossOfPower(vThresh=4.0):
            selfState["state"] = NodeState.SHUTDOWN


    # TODO: improve the logic here, it is a bit messy. maybe use draw a state diagram to help visualize it
    # ------------------ Change LEDs ------------------
    
    if selfState["state"] == NodeState.IDLE:
        led_4.value = 1.0
        led_17.value = 0.0
        led_22.value = 0.0
        led_27.value = 0.0
    if selfState["state"] == NodeState.BUSY:
        led_17.value = 1.0
        led_4.value = 0.0
        led_22.value = 0.0
        led_27.value = 0.0
    if selfState["state"] == NodeState.MIGRATING:
        led_22.value = 1.0
        led_4.value = 0.0
        led_17.value = 0.0
        led_27.value = 0.0
    if selfState["state"] == NodeState.SHUTDOWN:
        led_27.value = 1.0
        led_4.value = 0.0
        led_17.value = 0.0
        led_22.value = 0.0
    
    

    # ------------------ Execute State ------------------
    if selfState["state"] == NodeState.IDLE:
        process = getNewProcess()
        if process:
            IPalias(process.aliasIP, True)
            if process.start() == False:
                raise RuntimeError("Failed to start process thread. Process not started.")
            selfState["state"] = NodeState.BUSY
        else:
            if os.path.exists("/home/pi/force_shutdown.txt"):
                os.system("sudo rm -rf /home/pi/force_shutdown.txt")
                selfState["state"] = NodeState.SHUTDOWN

    if selfState["state"] == NodeState.BUSY:
        if process.procState == ProcessState.COMPLETED:
            # sendProcessResultsToUser() # TODO: if we want to send the results back to the user, we can do that here
            selfState["state"] = NodeState.IDLE

    if selfState["state"] == NodeState.MIGRATING:
        checkpointAndMigrateProcessToNode(process, findAvailableNode())
        selfState["state"] = NodeState.SHUTDOWN

    if selfState["state"] == NodeState.SHUTDOWN:
        if os.path.exists("/home/pi/force_idle.txt"):
            os.system("sudo rm -rf /home/pi/force_idle.txt")
            selfState["state"] = NodeState.IDLE

    return process


def main():
    global voltage, current, selfState

    # get the ip address of the current host and store it in the selfState dictionary
    selfState["ip"] = netifaces.ifaddresses('eth0')[2][0]['addr']

    try:
        # https://gpiozero.readthedocs.io/en/stable/api_input.html#mcp3008
        if useADC:
            voltage = MCP3008(channel=2, differential=False, max_voltage=5)  # single ended on channel 2
            current = MCP3008(channel=1, differential=True, max_voltage=5)  # differential on channel 1 and 0, might need to change to pin 0 if output is inverted
        broadcaster = BroadcastSender()  # Start broadcast sender and receiver threads
        broadcaster.start()
        receiver = BroadcastReceiver()
        receiver.start()
        process = None
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
            if not useADC:
                selfState["voltage"] = 0
                selfState["current"] = 0
            else:
                selfState["voltage"] = voltage.value
                selfState["current"] = current.value
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
                    uniqueOtherNodeStatuses[packet["ip"]] = (packet, time.time())
            except socket.timeout:  # TODO: This timout does not work since the socket will receive its own broadcast packets
                if self.timeout_reset_counter-1 == 0:
                    uniqueOtherNodeStatuses = {}      # If we don't receive anything within a period, clear
                    self.timeout_reset_counter = 8
            except Exception as e:                    # If we receive any exception, just print it and continue
                print(e)

    def stop(self):
        self._running = False


if __name__ == '__main__':  # if we are running in the main context
    global useADC
    useADC = True
    if 'noadc' in sys.argv:
        print("ADC disabled")
        useADC = False
        voltage, current = None, None
    main()
