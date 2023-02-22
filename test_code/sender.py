import os
import pickle
import random
import socket
import subprocess
import sys
import threading
import time
import pexpect
from enum import Enum, auto
from ipaddress import IPv4Address
from subprocess import Popen, PIPE


def main():
    try:
    # Main FSM
        state = 0



        while(True):
            if state == 0:
                migrate = input("Press any key to migrate")
                state = 1
            if state == 1:
                result = subprocess.run(['ps', 'ax'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # Get a list of all processes and find the one that is running socket_echo_client.py
                lines = result.stdout.decode().split('\n')
                matching_lines = [line for line in lines if "vidboardmain.py" in line]           # Find the line that contains socket_echo_client.py
                pid = matching_lines[0].split()[0]        
                print("Dumping: vidboardmain.py")
                print("PID: " + pid)                                             # Get the PID of the process from the first line
                os.system(f"sudo criu dump -vvvv -o dump.log -t {pid} --shell-job --tcp-established && echo OK")

                dst_ip = "192.168.137.140" # IP of the new server

                print("SCP /home/pi/videoboard folder to: " + dst_ip)
                # This is the expect script that will be run to transfer the dump file to the server
                # we use expect to automate the password prompt for scp/rsync so we don't have to type it in manually
                # expect_script = f"""
                # #!/usr/bin/expect
                # set timeout 30
                # spawn scp -r /home/pi/videoboard pi@{dst_ip}:/home/pi/
                # expect "password:"
                # send "pi\r"
                # expect eof
                # """
                # result = subprocess.run(['expect'], input=expect_script, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8')

                # proc = subprocess.Popen(['scp', '-r', '/home/pi/videoboard', 'pi@192.168.137.140:/home/pi',], stdin=subprocess.PIPE, stdout=subprocess.PIPE, 
                #         stderr=subprocess.PIPE)
                
                # proc.stdin.write('pi\n'.encode())
                # proc.stdin.flush()
                # stdout, stderr = proc.communicate()
                ssh_cmd = 'sudo scp -r /home/pi/videoboard pi@192.168.137.140:/home/pi/'                                                                                                               
                child = pexpect.spawn(ssh_cmd, timeout=30)  #spawnu for Python 3                                                                                                                          
                child.expect(['pi@192.168.137.140\'s password: '])                                                                                                                                                                                                                                                                                               
                child.sendline('pi') 
                child.expect(pexpect.EOF)  
                child.close()
                print("SCP Flag file")
                ssh_cmd = 'sudo scp /home/pi/flag.txt pi@192.168.137.140:/home/pi'                                                                                                               
                child = pexpect.spawn(ssh_cmd, timeout=30)  #spawnu for Python 3                                                                                                                          
                child.expect(['pi@192.168.137.140\'s password: '])                                                                                                                                                                                                                                                                                               
                child.sendline('pi') 
                child.expect(pexpect.EOF)  
                child.close()


                if result.returncode != 0:  # If the script failed
                    print("File transfer failed")
                print("Deleting IP alias")
                os.system(f"sudo ip addr del 192.168.137.2/24 dev eth0")
                print("Complete")
                break
                
    except (KeyboardInterrupt, Exception) as e:
       
        print("Exiting...")
        if not isinstance(e, KeyboardInterrupt):
            raise e




if __name__ == '__main__':  # if we are running in the main context
    main()  # run the main function. python is weird and this is how you do it
