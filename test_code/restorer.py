import os
import sys

os.system(f"unshare -p -m --fork --mount-proc")
os.system(f"ip addr add 192.168.137.2/24 dev eth0")

os.system(f"cd {sys.argv[1]}")
os.system(f"criu restore -vvvv -o restore.log --shell-job --tcp-established")
