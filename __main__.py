#!/usr/bin/micropython
import ace_of_states as ace
import ubus, logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("AOS Service")

""" Ace of States ubus service"""
Persistant_vault = ace.AOS_Persistant()
Temporary_vault = ace.AOS_Temporary()

def write(handler, data):
    persistant, label, variable, value =  data['persistant'], data['label'], data['variable'], data['value']
    if persistant:
        res = Persistant_vault.write(label, variable, value)
    else:
        res = Temporary_vault.write(label, variable, value)
    handler_reply(handler, {'Status': 'OK' if res else 'Fail'})

def read(handler, data):
    label, variable, persistant =  data['label'], data['variable'], data['persistant']
    if persistant:
        value = Persistant_vault.read(label, variable)
    else:
        value = Temporary_vault.read(label, variable)
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
    