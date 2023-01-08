import json
import os
import random
import shutil
import signal
import socket
import string
import subprocess
import sys
import threading
import time

state = "idle"
nodeIPaddrs = []
Process = ""
processID = ""
isManualCMD = ""


def handlePolling(state):
    """Respond to polling from other nodes with state information"""
    # *TCP current state to polling node*
    pass


def waitForProcessCMD() -> tuple:
    return True, "process"


def startProcessThread(process):
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


def waitForMigrateCMD() -> tuple[bool, bool]:
    """Handle migrate command"""
    if (isLossOfPower()):  # Check for loss of power or manual input command
        return True, False
    elif manualInput():
        return True, True
    else:
        return False, False


def sendFinishTransferFlag(username="pi", ip="1", password="pi", path=""):
    result = subprocess.run(["ssh", "-t", f"{username}@{ip}", "-p", f"{password}", f"touch {path}; exit"], stdout=subprocess.PIPE)
    if result.returncode == 0:
        print("File updated successfully")
    else:
        print("Failed to update file")


def pollNodeforState(address) -> str:
    """Poll node at given address to get state"""
    # *TCP address for Node State*
    statefromNode = "idle"
    return statefromNode


def waitForProcessCMD():
    # #Check specified directory for files
    # Process = (check directory, if not empty, then it should contain a process and checkpoint)
    # If Process != none
    # Return Process, true
    # Else
    # Return none, false
    pass


def CheckpointandSaveProcessToDisk(processID, process):
    """Handle case of no available nodes, checkpoint process to current working directory"""
    # *Run bash Script to checkpoint node and Save to receiving directory on current node*
    # *That way, on startup any files inside the directory will immediately be restored from
    # Checkpoint and resumed on system*
    pass


def checkpointAndMigrateProcessToNode(processID, process, ipToSend):
    # Handle checkpointing and migration
    # *Run bash Script to checkpoint node and SCP to address in specific directory*
    # *Delete process and supporting files on current node*
    pass


def migrateProcessToAvaliableNode(processID, process):
    global state
    ipToSend = None
    for address in nodeIPaddrs:
        state = pollNodeforState(address)
        if state == "idle":
            if ipToSend == None:
                ipToSend = address
            else:
                # * Possible comparison for other factors like time, weather, etc.*
                ipToSend = address
    if ipToSend == None:
        CheckpointandSaveProcessToDisk(processID, process)
    else:
        checkpointAndMigrateProcessToNode(processID, process, ipToSend)


def getProcessID(proc) -> int:
    # *Get process ID from process*
    # pid = subprocess.check_output(['pidof', 'f{proc}'])
    return 0  # pid


def criuDump(proc) -> bool:
    result = subprocess.check_output(['sudo', 'criu', 'dump', '-t', f'$(pgrep {proc})', '-v4', '-o', 'output.log', '&&', 'echo', 'OK'])
    if result == "OK":
        return True
    else:
        raise Exception(f"CRIU Dump Result: '{result}', Expected: OK")


def criuRestore(path) -> bool:
    result = subprocess.check_output(['sudo', 'criu', 'restore', '-d', '-v4', '-o', 'restore.log', '&&', 'echo', 'OK'])
    if result == "OK":
        return True
    else:
        raise Exception(f"CRIU Restore Result: '{result}', Expected: OK")


def sendProcessResultsToUser():
    # os.system("scp .....")
    # os.system("ssh to other node, create flag file. idk how to do this better")
    pass


def handleStates(state):
    """Main FSM"""
    match state:
        case "idle":  # Idle State, should look inside project directory for files to run
            processReceived, process = waitForProcessCMD()
            if processReceived:
                state = "processing"
                startProcessThread(process)

        case "processing":
            migrate, isManualCMD = waitForMigrateCMD()
            if migrate:
                state = "migrating"
                processID = getProcessID()  # If complete, send output logs or finished process results back to user
            elif process.isComplete():
                state = "idle"
                sendProcessResultsToUser()

        case "migrating":
            migrateProcessToAvaliableNode(processID, process)
            # if migration command is manual, then keep the node in idle, else send to shutdown state
            if isManualCMD:
                state = "idle"
            else:
                state = "shutdown"
        case "shutdown":
            # Node will shut down eventually with loss of power, but potentially leaving the option to return to
            # Idle state if power does return and node somehow still can operate
            if not isLossOfPower():
                state = "idle"
    return state


def saveNodeState(state: dict) -> None:
    # *Save node state to file*
    with open("state.json", "w", encoding='utf-8') as f:
        f.write(json.dumps(state))


if __name__ == '__main__':
    state = "idle"
    # while True:
    #    state = handleStates(state)
    #    handlePolling(state)
