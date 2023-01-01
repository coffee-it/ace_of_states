#!/usr/bin/micropython
"""
Варианты использования:
- Запуск ubus сервиса;
- импортировать как модуль для хранения локального состояния

TODO разделить на эти составляющие
"""
import uio, btree, ubus, logging, os, errno
from micropython import const

PERSISTANT_DB_PATH=const("/opt/ace_of_states")

logging.basicConfig(level=logging.DEBUG)
log_aos   = logging.getLogger("AOS")

def open_db_from_file(absolut_path):
    # File DB storage
    try:
        f = open(absolut_path, 'r+b')
    except:
        f = open(absolut_path, 'w+b')
    return f

def os_exists(path):
    try:
        return os.stat(path)[0]
    except Exception as e:
        errno = e.args[0]
        if errno == errno.ENOENT:
            return 0
        raise e

class Ace_of_States():
    def __init__(self, aos_local_vault = None) -> None:
        self.TEMP_IO_STREAMS  = {}
        self.PERSISTANT_FILES = {}
        if aos_local_vault:
            self.VAULT = btree.open(open_db_from_file(aos_local_vault))
        else:
            self.VAULT = btree.open(uio.BytesIO())

    def low_write(self, btreeIO, variable: str, value: str) -> bool:
        try:
            btreeIO.put(variable, str(value))
            btreeIO.flush()
        except Exception as e:
            log_aos.error("Low write error [%s, %s]" % (variable, value))
            log_aos.debug("%s" % e)
            return False
        else:
            return True
    def low_read(self, btreeIO, variable: str) -> str|None:
        value = btreeIO.get(str(variable))
        if value: return value.decode('utf-8')
        return None

    def temp_created(func):
        """Decorator which checks that the IO buffer is available"""
        def creation_checking(self, db_label, variable, value):
            if not db_label in self.TEMP_IO_STREAMS:
                log_aos.debug("[%s] Create btree IO instance" % db_label)
                self.TEMP_IO_STREAMS.update({db_label: btree.open(uio.BytesIO())})
            return func(self, db_label, variable, value)

        return creation_checking

    def persistant_created(func):
        """Decorator which checks that the DB file is available"""
        def creation_checking(self, db_label, variable, value):
            if not db_label in self.PERSISTANT_FILES:
                if not os_exists("%s/%s" % (PERSISTANT_DB_PATH, db_label)):
                    if not os_exists(PERSISTANT_DB_PATH):
                        os.mkdir(PERSISTANT_DB_PATH)
                    log_aos.debug("[%s] Create btree IO instance" % db_label)
                self.PERSISTANT_FILES.update({db_label: btree.open(open_db_from_file("%s/%s" % (PERSISTANT_DB_PATH, db_label)))})
            return func(self, db_label, variable, value)

        return creation_checking
    @temp_created
    def write_temporary(self, db_label:str, variable:str, value:str) -> bool:
        """Write to temporary storage"""
        if self.read_temporary(db_label, variable) == value:
            log_aos.debug("[%s] Variable %s is already \"%s\"" % (db_label, variable, value))
            return True
        log_aos.debug("[%s] Write %s to %s" % (db_label, value, variable))
        return self.low_write(self.TEMP_IO_STREAMS[db_label], variable, value)

    def read_temporary(self, db_label:str, variable:str, default:str = None) -> str|None:
        """Read from temporary storage"""
        if not db_label in self.TEMP_IO_STREAMS:
            log_aos.debug("Label %s not in TEMP_IO_STREAMS" % db_label)
            return default
        value = self.low_read(self.TEMP_IO_STREAMS[db_label], variable)
        return value if value else default

    @persistant_created
    def write_persistant(self, db_label, variable, value) -> bool:
        """Write to persistant storage"""
        if self.read_persistant(db_label, variable) == value:
            log_aos.debug("[%s] Variable %s is already %s" % (db_label, variable, value))
            return True
        log_aos.debug("[%s] Write %s to %s" % (db_label, value, variable))
        return self.low_write(self.PERSISTANT_FILES[db_label], variable, value)

    # @persistant_created
    def read_persistant(self, db_label:str, variable:str, default:str = None) -> str|None:
        """Read from persistant storage"""
        if not db_label in self.PERSISTANT_FILES:
            # but
            if os_exists("%s/%s" % (PERSISTANT_DB_PATH, db_label)):
                self.PERSISTANT_FILES.update({db_label: btree.open(open_db_from_file("%s/%s" % (PERSISTANT_DB_PATH, db_label)))})
            else:
                log_aos.debug("Label %s not in PERSISTANT_FILES" % db_label)
                return default
        value = self.low_read(self.PERSISTANT_FILES[db_label], variable)
        return value if value else default

    @staticmethod
    def safe_restore_type(typeclass, data: str):
        if type(data) != str:
            if isinstance(data, typeclass):
                return data
        try:
            return typeclass(data)
        except (ValueError):
            log_aos.warning("Something went wrong with %s(%s)" % (typeclass, data))
        return None

    @staticmethod
    def restore_type(typeclass: str, data: str):
        if type(data) != str:
            if isinstance(data, typeclass):
                return data
        else:
            try:
                ff = compile("%s(%s)" % (str(typeclass), str(data)), 'file', 'eval')
                zz = eval(ff)
                return zz
            except (SyntaxError, ValueError):
                log_aos.warning("Something went wrong with %s(%s)" % (typeclass, data))
            except:
                log_aos.warning("Failed %s type resoring of %s" % (data))
        return False



""" Ace of States ubus service"""
AOS_Service = Ace_of_States()

def write(handler, data):
    persistant, label, variable, value =  data['persistant'], data['label'], data['variable'], data['value']
    if persistant:
        res = AOS_Service.write_persistant(label, variable, value)
    else:
        res = AOS_Service.write_temporary(label, variable, value)
    handler_reply(handler, {'Status': 'OK' if res else 'Fail'})

def read(handler, data):
    label, variable, persistant =  data['label'], data['variable'], data['persistant']
    if persistant:
        value = AOS_Service.read_persistant(label, variable)
    else:
        value = AOS_Service.read_temporary(label, variable)
    handler_reply(handler, {variable: value})

def drop(handler, data):
    """DROPDATABASE"""
    handler_reply(handler, {'Status': 'Priplily'})

def handler_reply(handler, reply):
    log_aos.debug("Reply %s" % reply)
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
        }},
    "drop": {"method": drop, "signature": {}}
    }
)
try:
    ubus.loop()
except KeyboardInterrupt:
    ubus.disconnect()