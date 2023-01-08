import random
import socket
import time

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

while True:
    node = random.randint(139, 143)  # random node just for testing
    with open(f"exampleState_{node}.json", "r") as f:
        data = f.read()
    print(f"Sending from Node {node}")  # remove newlines and tabs from data
    s.sendto(bytes(data, encoding="utf-8"), ('255.255.255.255', 12345))
    time.sleep(0.2)
