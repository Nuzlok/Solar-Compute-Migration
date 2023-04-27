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
    """ Enum for the state of the node. This is used to determine if the node can accept processes or not"""
    IDLE = auto()			# Node is idle and ready to accept
    BUSY = auto()			# Node is busy with processes and cannot accept processes
    MIGRATING = auto()  	# Node is migrating to another and cannot accept processes
    SHUTDOWN = auto()		# Node is shutting down and cannot accept processes

    def __str__(self):
        return self.name


class ProcessState(Enum):
    """ Enum for the state of the process. This is used to determine if the process is running or not. Currently, this is not used. """
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
uniqueOtherNodeStatuses = {}  # set of unique statuses from other nodes (all nodes except this one). key is IP address, value is status
DIRECTORY = "/home/pi/ReceivedProcesses/"  # directory to store processes that are received from other nodes (Currently not used)
ADC_Values = [(0,0)] * 5  # Store ADC values to smooth  using a moving average
led_4 = PWMLED(4)  # LED on pin 4 (These LEDs are to show the status of the node during Expo)
led_17 = PWMLED(17)  # LED on pin 17
led_27 = PWMLED(27)  # LED on pin 27
led_22 = PWMLED(22)  # LED on pin 22

class Process:
    """
    Contains all the information about a process and provides functions to start, stop, and terminate the process.
    TODO: convert to a dataclass instead of a normal class. This will make the code more readable and easier to use
    """

    def __init__(self, name: str, location=None, aliasIP=None):
        self.procState = ProcessState.NONE # The state of the process. This is set when the process is started
        self.procName = name
        self.location = location
        self.aliasIP = aliasIP  # getAvailableIP()  # TODO: get an available IP address for the process (check list of used IPs and invert that list)
        self.pid = None # the PID of the process. This is set when the process is started

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
        # os.system(f"setsid nohup sudo {command} </dev/null &>/dev/null &")
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

        # TODO: get the PID of the process after it is restored (Does not work for unknown reason)
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

        # Delete any preexisting dump files in the directory (This is to prevent multiple dumps files interfeering)
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


def isLossOfPower(vThresh=12, vScale=55, cScale=10) -> bool:
    """ Decide when node is losing power by comparing the voltage and current to a threshold. """
    # get the rolling average of the last 5 values

    # TODO: remove the whole current section, since current is used to measure power consumption, not power loss
    
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
    if isLossOfPower() or forceMigrate: # if the node is losing power from PV, then migrate
        return True

    # TODO: probably remove this whole migrate_cmd section, since unused
    # -----------------------------
    global selfState
    if selfState["migrate_cmd"] == True: 
        selfState["migrate_cmd"] = False
        return True
    # -----------------------------

    if os.path.exists("/home/pi/force_migrate.txt"): # if the file exists, then the HMI has requested a migration
        os.system("rm -rf /home/pi/force_migrate.txt")
        return True
    return False


def sendFinishFlag(path: str, ip: IPv4Address, username="pi", password="pi") -> None:
    """ 
    Send a flag to the destination node to indicate that the file transfer is complete.
    without this flag, the destination node will not know when transfer is complete
    or if an error occurred during the transfer.
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
    Check specified directory for a flag file indicating when files are complete and ready to run.
    if files are found with the flag, create a process dataclass and return it.
    """
    # global DIRECTORY # Not sure if I need this or not.

    # TODO: try to use the commented out section below to set up the process, instead of hardcoding it
    # TODO: change the way you look for files so you can handle multiple processes

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
    start_time_ms = int(time.time()*1000) # get the start time in milliseconds for timing information
    if proc.dump() == False:
        raise Exception("Failed to checkpoint process, dumping failed")
    print("Process dumped successfully")
    dump_time_ms = int(time.time()*1000)

    # if confirmNodeAvailable(receivingIP) == False: # TODO: implement this function, currently not tested working
    #     raise Exception("Receiving node is not responding/available")
    # print(f"Confirmed node at {receivingIP} is available")
    # confirm_time_ms = int(time.time()*1000)

    if IPalias(proc.aliasIP, False) == False:
        raise Exception("Failed to remove IP alias from current node, new node will not be able to run networked process")
    print("IP alias removed from current node")
    alias_time_ms = int(time.time()*1000)

    if receivingIP == None: # If no nodes are available, then make a flag file to indicate that the process is ready to run on this node again
        os.system("touch /home/pi/cpflag.txt")
        return True
    # else:
    
    # this means other nodes are available, so we can migrate the process to another node
    if rsyncProcessToNode(proc, receivingIP) == False:
        raise Exception("Failed to rsync process to receiving node, transfer may be incomplete")
    print("Process rsynced to receiving node")
    rsync_time_ms = int(time.time()*1000)

    if sendFinishFlag(ip=receivingIP, path=proc.procName) == False:
        raise Exception("Failed to send finish flag to receiving node, process might not start")
    print("Finish flag sent to receiving node")
    flag_time_ms = int(time.time()*1000)

    if proc.deleteFromDisk() == False:  
        raise Exception("Failed to delete process from disk, process might accidentally run again on this node")
    print("Process deleted from disk")
    delete_time_ms = int(time.time()*1000)

    bar_width = 50 # width of the bar graph

    total_time_ms = delete_time_ms-start_time_ms
    with open("/home/pi/migrate_stats.txt", "w") as f: # write timing information to a file
        f.write(f"Time: {time.time()}")
        f.write(f"Migration took total of {total_time_ms} ms\n")
        f.write(f"{'Dumping':<15} {dump_time_ms-start_time_ms:2.0f} ms {'-'*int((dump_time_ms-start_time_ms)/total_time_ms*bar_width)}\n")
        f.write(f"{'IP alias (rem)':<15} {alias_time_ms-dump_time_ms:2.0f} ms {'-'*int((alias_time_ms-dump_time_ms)/total_time_ms*bar_width)}\n")
        f.write(f"{'Rsyncing':<15} {rsync_time_ms-alias_time_ms:2.0f} ms {'-'*int((rsync_time_ms-alias_time_ms)/total_time_ms*bar_width)}\n")
        f.write(f"{'Finish flag':<15} {flag_time_ms-rsync_time_ms:2.0f} ms {'-'*int((flag_time_ms-rsync_time_ms)/total_time_ms*bar_width)}\n")
        f.write(f"{'Deleting':<15} {delete_time_ms-flag_time_ms:2.0f} ms {'-'*int((delete_time_ms-flag_time_ms)/total_time_ms*bar_width)}\n")

    proc = None  # remove the process from memory after it has been migrated, not sure if this does anything
    return True


def rsyncProcessToNode(proc: Process, ip: IPv4Address, password="pi", username="pi"):
    """ 
    Copy the dumped files to the receiving node
    Consider using rsync instead of scp, **it is more efficient and can resume transfers if they are interrupted**
    """
    procname = "videoboard"
    
    # ssh_cmd = f'sudo rsync -avz /home/pi/{proc.getDirectory()} {username}@{ip}:{DIRECTORY}'
    ssh_cmd = f'sudo scp -r /home/pi/{procname} {username}@{ip}:/home/pi/'
    child = pexpect.spawn(ssh_cmd, timeout=30)
    child.expect([f"{username}@{ip}'s password: "])
    child.sendline(f'{password}')
    child.expect(pexpect.EOF)
    child.close()
    return child.exitstatus == 0

# def IPalias(address: IPv4Address, add: bool) -> bool:
#     """Handle IP alias to current node. set add to true to add alias, and vice versa
#        This version is to allow multiple IP aliases to be added to the node for multiple processes.
#        This will be used in the future when we have multiple processes running on the same node
#     """
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
    """Handle IP alias to current node. set add to true to add alias, and vice versa.
       returns true if the command was successful, false otherwise
    """
    if add:
        return os.system(f"ip addr add {address}/24 dev eth0") == 0
    return os.system(f"ip addr del {address}/24 dev eth0") == 0


def findAvailableNode() -> IPv4Address:
    """Find an available node to migrate to """
    available = []
    for packet, time in uniqueOtherNodeStatuses.values(): # loop through all the nodes
        if packet["state"] == NodeState.IDLE:  # found an available node since it is idle
            available.append(packet["ip"])

    # TODO: Possible comparison for other factors like time, weather, etc.. here. For now, just return the first available node
    if len(available) > 0:
        return available[0]
    return None


def confirmNodeAvailable(ip: IPv4Address) -> bool:
    """Confirm that the node is available to receive a process.
    if the node does not respond within 10 seconds, it is considered unavailable
    return true if the node is available, false otherwise"""
    last_time = uniqueOtherNodeStatuses[ip][1]
    while time.time() < last_time + 10:  # wait maximum 10 seconds for a new packet from the node
        if uniqueOtherNodeStatuses[ip][1] > last_time:
            return True # node sent a new packet, it is available
    return False  # timed out, node is not available


def MainFSM(process: Process):
    global selfState
    time.sleep(0.05)  # make sure it doesnt hog the CPU by sleeping for a bit

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

    # ------------------ Change LEDs ------------------
    # This is just for the Demo to show the state of the node.
    # Can be omitted without side effects. 
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
    
    
    # TODO: improve the logic here, it is a bit messy. maybe use draw a state diagram to help visualize it
    # ------------------ Execute State ------------------
    if selfState["state"] == NodeState.IDLE:
        process = getNewProcess() 
        if process: # if there is a new process to run
            IPalias(process.aliasIP, True)
            if process.start() == False:
                raise RuntimeError("Failed to start process thread")
            selfState["state"] = NodeState.BUSY # change state to busy if the process started successfully
        else:
            if os.path.exists("/home/pi/force_shutdown.txt"): # if the HMI requested a shutdown
                os.system("sudo rm -rf /home/pi/force_shutdown.txt")
                selfState["state"] = NodeState.SHUTDOWN

    if selfState["state"] == NodeState.BUSY:
        if process.procState == ProcessState.COMPLETED: # if the process exited
            # sendProcessResultsToUser() # TODO: if we want to send the results back to the user, we can do that here
            selfState["state"] = NodeState.IDLE

    if selfState["state"] == NodeState.MIGRATING:
        checkpointAndMigrateProcessToNode(process, findAvailableNode()) # The main function that handles the migration process
        selfState["state"] = NodeState.SHUTDOWN

    if selfState["state"] == NodeState.SHUTDOWN: # This is a "virtual" state. used to simulate a node that is shutting down. 
        if os.path.exists("/home/pi/force_idle.txt"): # if the HMI requested to go back to idle
            os.system("sudo rm -rf /home/pi/force_idle.txt")
            selfState["state"] = NodeState.IDLE

    return process # return the process so that it can be passed to the next iteration of the loop


def main():
    global voltage, current, selfState

    # get the ip address of the current host and store it in the selfState dictionary
    selfState["ip"] = netifaces.ifaddresses('eth0')[2][0]['addr']

    try:
        # https://gpiozero.readthedocs.io/en/stable/api_input.html#mcp3008
        if useADC:
            voltage = MCP3008(channel=2, differential=False, max_voltage=5)  # single ended on channel 2
            current = MCP3008(channel=1, differential=True, max_voltage=5)  # differential on channel 1 and 0, might need to change to pin 0 if output is inverted
        broadcaster = BroadcastSender()  # Start broadcast sender thread
        broadcaster.start()
        receiver = BroadcastReceiver() # Start broadcast receiver thread
        receiver.start()
        process = None
        print(f"reading voltage from pin 2, current from pin 0-1")
        while True:
            process = MainFSM(process)  # Main FSM loop forever until interrupted
    except (KeyboardInterrupt, Exception) as e:
        broadcaster.stop()
        broadcaster.join()
        receiver.stop()
        receiver.join()
        # for alias in selfState["ip_alias"]: # remove all the aliases that were created. 
        #     IPalias(alias, False)
        print("Exiting...")
        if not isinstance(e, KeyboardInterrupt): # FIXME if the exception is anything other than a keyboard interrupt,
            # then we want to raise it so that we can see what it is. This doesnt work properly right now
            raise e


class BroadcastSender(threading.Thread):
    """ 
    This class is used to create a thread that sends broadcast packets to other nodes. 
    The packets contain the node's current state and IP address.
    """

    def __init__(self, address='255.255.255.255', port=12345):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1) # enable broadcast
        self.send_delay = 0.2 # how often to send broadcast packets
        self.baddress = address # broadcast address
        self.port = port # broadcast port
        self._running = True # sentinel value for the thread
        super().__init__()

    def run(self):
        global selfState
        while self._running: # loop till the sentinel value is set
            if not useADC: # if we are not using the ADC, then set the voltage and current to 0
                selfState["voltage"] = 0
                selfState["current"] = 0
            else:
                selfState["voltage"] = voltage.value # get the readings from the ADC
                selfState["current"] = current.value
            self.socket.sendto(pickle.dumps(selfState), (self.baddress, self.port)) # broadcast the state
            time.sleep(self.send_delay)
        print("Closing Socket!")
        self.socket.close()
        print("Stopped Broadcast!")

    def stop(self):
        self._running = False # set the sentinel value to stop the thread


class BroadcastReceiver(threading.Thread):
    """This class is used to listen for incoming broadcast status packets from the nodes so each node can know the status of the other nodes"""

    def __init__(self):
        self._running = True # sentinel value for the thread
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
                packet = pickle.loads(self.sock.recvfrom(self.sockSize)[0]) # receive a packet and deserialize it
                if packet["ip"] != selfState["ip"]:                         # If the packet is not from this node
                    uniqueOtherNodeStatuses[packet["ip"]] = (packet, time.time()) # Add the packet to the dictionary
            except socket.timeout:  # TODO: This timout does not work since the socket will receive its own broadcast packets
                if self.timeout_reset_counter-1 == 0:
                    uniqueOtherNodeStatuses = {}      # if we have timed out 8 times, clear the dictionary
                    self.timeout_reset_counter = 8
            except Exception as e:                    # any exception, ignore and continue
                print(e)

    def stop(self):
        self._running = False # set the sentinel value to stop the thread


if __name__ == '__main__':  # if we are running in the main context
    global useADC
    useADC = True # by default, use the ADC unless specified
    if 'noadc' in sys.argv:
        print("ADC disabled") # allow the ADC to be disabled for testing purposes. this will make it so that the node will NOT migrate by itself. will always require HMI to initiate migration
        useADC = False
        voltage, current = None, None
    main() # run the main function
