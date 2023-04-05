
import RPi.GPIO  # ensure pin factory is set to RPi.GPIO
import spidev  # only for gpio pins on raspberry pi
from gpiozero import MCP3008
from time import sleep
import os

voltage = MCP3008(channel=2)

while voltage.value > 5:
    sleep(0.1)

os.system("sudo fallocate -l 4G /home/pi/4Gbfile")
os.system("sudo time scp 4Gbfile pi@192.168.137.141:/home/pi/")
