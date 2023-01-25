#!/usr/bin/micropython
from ace_of_states.multiple import Persistant, Temporary
import ubus, logging

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("AOS Service")

""" Ace of States ubus service"""
AOS_Persistant = Persistant()
AOS_Temporary = Temporary()

def write_persistant(handler, data):
    label, variable, value = data['label'], data['variable'], data['value']
    res = AOS_Persistant.write(label, variable, value)
    handler_reply(handler, {'Status': 'OK' if res else 'Fail'})

def read_persistant(handler, data):
    label, variable = data['label'], data['variable']
    value = AOS_Persistant.read(label, variable)
    handler_reply(handler, {variable: value})

def write_temporary(handler, data):
    label, variable, value = data['label'], data['variable'], data['value']
    res = AOS_Temporary.write(label, variable, value)
    handler_reply(handler, {'Status': 'OK' if res else 'Fail'})

def read_temporary(handler, data):
    label, variable = data['label'], data['variable']
    value = AOS_Temporary.read(label, variable)
    handler_reply(handler, {variable: value})


def drop(handler, data):
    """DROPDATABASE"""
    handler_reply(handler, {'Status': 'Priplily'})

def handler_reply(handler, reply):
    logger.debug("Reply %s" % reply)
    handler.reply(reply)

ubus.connect('/var/run/ubus.sock')
ubus.add("aos_persistant", {
    "write": {"method": write_persistant, "signature": {
        "label": ubus.BLOBMSG_TYPE_STRING,
        "variable":  ubus.BLOBMSG_TYPE_STRING,
        "value":  ubus.BLOBMSG_TYPE_STRING
        }},
    "read": {"method": read_persistant, "signature": {
        "label": ubus.BLOBMSG_TYPE_STRING,
        "variable":  ubus.BLOBMSG_TYPE_STRING
        }}
    }
)
ubus.add("aos_temporary", {
    "write": {"method": write_temporary, "signature": {
        "label": ubus.BLOBMSG_TYPE_STRING,
        "variable":  ubus.BLOBMSG_TYPE_STRING,
        "value":  ubus.BLOBMSG_TYPE_STRING
        }},
    "read": {"method": read_temporary, "signature": {
        "label": ubus.BLOBMSG_TYPE_STRING,
        "variable":  ubus.BLOBMSG_TYPE_STRING
        }}
    }
)
try:
    ubus.loop()
except KeyboardInterrupt:
    ubus.disconnect()
    