import random
import socket
import time

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    while True:
        node = random.randint(139, 143)  # random node just for testing
        with open(f"exampleState_{node}.json", "r") as f:
            data = bytes(f.read().encode("utf-8"))
        print(f"Sending from Node {node}")

        s.sendto(data, ('255.255.255.255', 12345))
        time.sleep(0.2)
