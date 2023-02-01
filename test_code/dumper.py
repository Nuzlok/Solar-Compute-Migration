import os
import subprocess
import sys

dst_ip = sys.argv[1]  # IP of the server
# ## ON LAPTOP
# socket_echo_server.py with IP of ethernet port (I used 192.168.137.1)
# python3 socket_echo_server.py 192.168.137.1

# ## ON PI
# Make testserver folder and put socket_echo_client.py inside
os.system(f"ip addr add 192.168.137.2/24 dev eth0")

# ### Run client (hard coded to bind to IP alias above) to connect to server
# python3 socket_echo_client.py 192.168.137.1
# ### Should see communication between client and server now

result = subprocess.run(['ps', 'ax'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # Get a list of all processes and find the one that is running socket_echo_client.py
lines = result.stdout.decode().split('\n')
matching_lines = [line for line in lines if "socket_echo_client.py" in line]           # Find the line that contains socket_echo_client.py
pid = matching_lines[0].split()[0]                                                     # Get the PID of the process from the first line


os.system(f"sudo criu dump -vvvv -o dump.log -t {pid} --shell-job --tcp-established && echo OK")

# This is the expect script that will be run to transfer the dump file to the server
# we use expect to automate the password prompt for scp so we don't have to type it in manually
expect_script = f"""
#!/usr/bin/expect
set timeout 30
spawn scp /home/pi/testserver pi@{dst_ip}:/home/pi/
expect "password:"
send "pi\r"
expect eof
"""

# Run the Expect script
result = subprocess.run(['expect'], input=expect_script, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')

if result.returncode != 0:  # If the script failed
    print("File transfer failed")
    exit()


os.system(f"sudo ip addr del 192.168.137.2/24 dev eth0")
