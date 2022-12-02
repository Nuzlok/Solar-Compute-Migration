# Main loop for algorithm
main():
	# Initialize startup state and enter loop
	state = idle
	while(true):
		handleStates(state)
		handlePolling(state)

# Respond to polling from other nodes with state information
handlePolling(state):
	*Send current state to polling node*

# Decide when node is losing power
isLossOfPower():
	Voltage = readVoltagefromGPIO
	Current = readCurrentfromGPIO
	if (voltage or current below some threshold):
		return true
	else: return false


# Globals for handleStates
Process
processID
isManualCMD

# Main FSM of system
handleStates(state):
	# Idle State, should look inside project 
	# directory for files to run
	if state == idle:
		processReceived, process = waitForProcessCMD()
		if processReceived:
			state = processing
			startProcessThread(process)
	# Processing State, continue processing until
	# finished or until migration command initiated
	if state == processing:
		migrate, isManualCMD = waitForMigrateCMD()
		# Given a user request, a recurring process’ log is sent to the user 
		request = userLogRequest()
		if request:
			sendOutputLogToUser()
		if migrate:
			state = migrating
			processID = getProcessID()
		# If complete, send output logs or finished process results back to user
elif (Process complete):
			state = idle
			sendOutputLogToUser()
	# Migration state, should pick an available node based off criterion, and send the checkpoint and   # supporting files to node	
	if state == migrating:
		migrateProcessToAvaliableNode(processID, process)
		# If migration command is manual, then keep the node in idle, else send to shutdown state
		if isManualCMD:
			state = idle
		else:
			state = shutdown
	# Node will shut down eventually with loss of power, but potentially leaving the option to return to 
	# Idle state if power does return and node somehow still can operate
	if state == shutdown:
		if isLossOfPower() == false:
			state = idle

# Handle starting a process
startProcessThread(process):
	if no checkpoint:
		*Start Process in separate thread*
	elif checkpoint:
		*Start process in separate thread and resume from checkpoint*

# Hard Coded Static Variables 
nodeIPaddrs = [List of node IPaddrs]
migrateProcessToAvaliableNode(processID, process):
	ipToSend = none
	for address in nodeIPaddrs:
		State = pollNodeforState(address)
		if state = idle:
			if ipToSend == none
				ipToSend = address
			else *Possible comparison for other factors like time, weather, etc.*
				ipToSend = address
	if ipToSend == None:
		CheckpointandSaveProcessToDisk(processID, process)
	else:
		checkpointAndMigrateProcessToNode(processID, process, ipToSend)

# Poll node at given address to get state
pollNodeforState(address):
	*Send address for Node State*
	return statefromnode


# Handle migrate command
waitForMigrateCMD():
	# Check for loss of power or manual input command
	if (isLossOfPower()):
		return true, false
	else if manualInput():
		return true, true
	else:
		return false, false

# Check specified directory for files
waitForProcessCMD():
	Process = # check directory, if not empty, then it should contain a process and checkpoint
	if Process != none:
		return Process, true
	else:
		return none, false

# Handle checkpointing and migration
checkpointAndMigrateProcessToNode(processID, process, ipToSend):
	# *Run bash Script to checkpoint node and SCP to address in specific directory*
	# *Delete process and supporting files on current node*

# Handle case of no available nodes, checkpoint process to current working directory
CheckpointandSaveProcessToDisk(processID, process):
	# *Run bash Script to checkpoint node and Save to receiving directory on current node*
	# *That way, on startup any files inside the directory will immediately be restored from Checkpoint and resumed on system*

