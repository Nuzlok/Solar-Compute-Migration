import socket
import time

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

while True:
	s.sendto(bytes(open("exampleState.json", "r").read(), encoding="utf-8"), ('255.255.255.255', 12345))
	time.sleep(1)
