import json
import os
import socket

from flask import Flask, redirect
from flask_restful import Api, Resource, abort, fields, marshal_with, reqparse


class index(Resource):
	def get(self):
		return json.loads(open("exampleState.json", "r").read())


def not_found(error):
	return f"404 not found: {error}"


class changeNode(Resource):
	def get(self, dst_node):
		if dst_node not in nodeIPs:
			abort(404, message="Node not found")


class refreshNodesListDefault(Resource):
	def get(self):
		# refresh()
		return "200"


def refresh(mask=24):
	"""
	be careful with this function. it does not work yet and I dont
	really know what happens if you run it
	"""
	global nodeIPs
	nodeIPs = []
	# os.system("sudo arp-scan -x -q -l -g") # scan the local subnet and ask which nodes are alive
	while selfIP in nodeIPs:
		nodeIPs.remove(selfIP)


if __name__ == '__main__':
	selfIP = socket.gethostbyname(socket.gethostname())
	nodeIPs = ["192.168.137.139", "192.168.137.140", "192.168.137.141", "192.168.137.142", "192.168.137.143"]
	refresh()

	app = Flask(__name__)
	api = Api(app)

	api.add_resource(refreshNodesListDefault, "/refreshNodesList")
	api.add_resource(changeNode, "/changeNode/<dst_node>")
	api.add_resource(index, "/")
	app.register_error_handler(404, not_found)

	app.run(host='0.0.0.0', debug=True)
