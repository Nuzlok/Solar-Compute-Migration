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
        print("Current working directory: {0}".format(os.getcwd()))
        while(True):
            isFolderExist = os.path.exists('/home/pi/videoboard')
            print("No Folder")
            if isFolderExist:
                print("No Flag File")
                while True:
                    isFlagFileExist = os.path.exists('/home/pi/videoboard/flag.txt')
                    if isFlagFileExist:
                        print("Flag File Found")
                        os.chdir('/home/pi/videoboard')
                        print("Current working directory: {0}".format(os.getcwd()))
                        os.system(f"cd /home/pi/videoboard")
                        os.system(f"sudo ip addr add 192.168.137.2/24 dev eth0")
                        os.system(f"unshare -p -m --fork --mount-proc criu restore -vvvv -o restore.log --shell-job --tcp-established")
                        break
                break
           
                
    except (KeyboardInterrupt, Exception) as e:
       
        print("Exiting...")
        if not isinstance(e, KeyboardInterrupt):
            raise e




if __name__ == '__main__':  # if we are running in the main context
    main()  # run the main function. python is weird and this is how you do it
