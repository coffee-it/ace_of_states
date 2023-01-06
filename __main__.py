#!/usr/bin/micropython
import ace_of_states as ace
import ubus, logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("AOS Service")

""" Ace of States ubus service"""
ACE_Persistant = ace.Persistant()
ACE_Temporary = ace.Temporary()

def write(handler, data):
    persistant, label, variable, value =  data['persistant'], data['label'], data['variable'], data['value']
    if persistant:
        res = ACE_Persistant.write(label, variable, value)
    else:
        res = ACE_Temporary.write(label, variable, value)
    handler_reply(handler, {'Status': 'OK' if res else 'Fail'})

def read(handler, data):
    label, variable, persistant =  data['label'], data['variable'], data['persistant']
    if persistant:
        value = ACE_Persistant.read(label, variable)
    else:
        value = ACE_Temporary.read(label, variable)
    handler_reply(handler, {variable: value})

def drop(handler, data):
    """DROPDATABASE"""
    handler_reply(handler, {'Status': 'Priplily'})

def handler_reply(handler, reply):
    logger.debug("Reply %s" % reply)
    handler.reply(reply)

ubus.connect('/var/run/ubus.sock')
ubus.add("aos", {
    "write": {"method": write, "signature": {
        "persistant": ubus.BLOBMSG_TYPE_BOOL,
        "label": ubus.BLOBMSG_TYPE_STRING,
        "variable":  ubus.BLOBMSG_TYPE_STRING,
        "value":  ubus.BLOBMSG_TYPE_STRING
        }},
    "read": {"method": read, "signature": {
        "persistant": ubus.BLOBMSG_TYPE_BOOL,
        "label": ubus.BLOBMSG_TYPE_STRING,
        "variable":  ubus.BLOBMSG_TYPE_STRING
        }} #,
    # "drop": {"method": drop, "signature": {}}
    }
)
try:
    ubus.loop()
except KeyboardInterrupt:
    ubus.disconnect()
    