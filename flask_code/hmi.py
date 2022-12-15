import os
import socket

from flask import *
from scapy.all import ARP, Ether, srp

# nodeIPs = {"1": "http://127.0.0.1/", "2": "http://127.0.0.2/"}
nodeIPs = []

app = Flask(__name__)


@app.route('/', methods=('GET', 'POST'))
def index():
    return render_template("index.html")


@ app.errorhandler(404)
def not_found(e):
    return render_template("404.html")


@app.route('/changeNode/<dst_node>')
def changeNode(dst_node):
    # return redirect(f"https://{nodeIPs[dst_node]}/", code=308)
    return render_template("index.html")


@app.route('/refreshNodesList')
def refreshNodesListDefault():
    # refresh()
    return render_template("index.html")


@app.route('/refreshNodesList/<ip>/<mask>')
def refreshNodesList(ip, mask):
    # refresh(f"{ip}/{mask}")
    return render_template("index.html")


# ---------------------------------------------------------------
# be careful with this function. it does not work yet and I dont
# really know what happens if yu run it
# ---------------------------------------------------------------
def refresh(target_ip="192.168.1.1/24"):
    arp = ARP(pdst=target_ip)  # create ARP packet
    packet = Ether(dst="ff:ff:ff:ff:ff:ff") / arp  # stack them
    ans, _ = srp(packet, timeout=3, verbose=0)

    clients = []
    for _, received in ans:
        clients.append({'ip': received.psrc, 'mac': received.hwsrc})
        nodeIPs.append(received.psrc)
    # print clients
    print("Available devices in the network:")
    print("IP" + " "*18+"MAC")
    for client in clients:
        print("{:16}    {}".format(client['ip'], client['mac']))

    # items = sorted(ipCount.items(), key=lambda item: socket.inet_aton(item[0]))


if __name__ == '__main__':
    app.run(host='0.0.0.0')
