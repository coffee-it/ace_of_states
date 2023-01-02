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

def os_exists(path):
    try:
        return os.stat(path)[0]
    except Exception as e:
        errno = e.args[0]
        if errno == errno.ENOENT:
            return 0
        raise e

class Ace_of_States_Basis():
    def __init__(self, aos_local_vault = None) -> None:
        self.TEMP_IO_STREAMS  = {}
        self.PERSISTANT_FILES = {}
        if aos_local_vault:
            self.VAULT = btree.open(self.open_db_from_file(aos_local_vault))
        else:
            self.VAULT = btree.open(uio.BytesIO())

    def open_db_from_file(self, absolut_path):
        # File DB storage
        try:
            f = open(absolut_path, 'r+b')
        except:
            f = open(absolut_path, 'w+b')
        return f

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

    def transform_value(func):
        """ Декоратор, проверяет значения и трансформирует в int"""
        def banana_transform(self, db_label, variable, value):
            """TODO распихать математику обратно по декорируемым функциям"""
            # db_label, variable, value = args
            _old = self.read(db_label=db_label, variable=variable)
            _old = _old if _old != None else 0
            _old = int(_old) if str(_old).isdigit() else 0
            _new = int(value) if str(value).isdigit() else 0
            if func.__name__ ==  "plus":
                _new = _old + _new
            elif func.__name__ ==  "minus":
                _new = _old - _new
            elif func.__name__ == "join":
                if _new < _old:
                    _new = _old + _new
                else:
                    _new = _old + (_new - _old)
            elif func.__name__ == "add":
                if _new >= _old:
                    _new = _old + (_new - _old)
                else:
                    log_aos.debug("Cant add. Value of %s from %s is less then current" % (variable, db_label))

            self.write(db_label=db_label, variable=variable, value=_new)
            
        return banana_transform
    @transform_value
    def plus(self, db_label, variable, value):
        """ Прибавляет value к текущему значению variable """
        pass
    @transform_value
    def minus(self, db_label, variable, value):
        """ Вычитает value из текущего значения variable """
        pass
    @transform_value
    def join(self, db_label, variable, value):
        """
        Добавляет к variable изменение(разность м/у новым и текущим) value.
        Если новое значение меньше - прибавляем полностью.
        """
        pass
    @transform_value
    def add(self, db_label, variable, value):
        """
        Добавляет к variable разность м/у новым и текущим значением value
        если новое значение превышает текущее. В противном случае оставляем без изменений.
        """

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

class AOS_Persistant(Ace_of_States_Basis):
    def persistant_created(func):
        """Decorator which checks that the DB file is available"""
        def creation_checking(self, db_label, variable, value):
            if not db_label in self.PERSISTANT_FILES:
                if not os_exists("%s/%s" % (PERSISTANT_DB_PATH, db_label)):
                    if not os_exists(PERSISTANT_DB_PATH):
                        os.mkdir(PERSISTANT_DB_PATH)
                    log_aos.debug("[%s] Create btree IO instance" % db_label)
                self.PERSISTANT_FILES.update({db_label: btree.open(self.open_db_from_file("%s/%s" % (PERSISTANT_DB_PATH, db_label)))})
            return func(self, db_label, variable, value)
        return creation_checking
    @persistant_created
    def write(self, db_label, variable, value) -> bool:
        """Write to persistant storage"""
        if self.read(db_label, variable) == value:
            log_aos.debug("[%s] Variable %s is already %s" % (db_label, variable, value))
            return True
        log_aos.debug("[%s] Write %s to %s" % (db_label, value, variable))
        return self.low_write(self.PERSISTANT_FILES[db_label], variable, value)

    def read(self, db_label:str, variable:str, default:str = None) -> str|None:
        """Read from persistant storage"""
        if not db_label in self.PERSISTANT_FILES:
            # but
            if os_exists("%s/%s" % (PERSISTANT_DB_PATH, db_label)):
                self.PERSISTANT_FILES.update({db_label: btree.open(self.open_db_from_file("%s/%s" % (PERSISTANT_DB_PATH, db_label)))})
            else:
                log_aos.debug("Label %s not in PERSISTANT_FILES" % db_label)
                return default
        value = self.low_read(self.PERSISTANT_FILES[db_label], variable)
        return value if value else default

class AOS_Temporary(Ace_of_States_Basis):
    def temp_created(func):
        """Decorator which checks that the IO buffer is available"""
        def creation_checking(self, db_label, variable, value):
            if not db_label in self.TEMP_IO_STREAMS:
                log_aos.debug("[%s] Create btree IO instance" % db_label)
                self.TEMP_IO_STREAMS.update({db_label: btree.open(uio.BytesIO())})
            return func(self, db_label, variable, value)

        return creation_checking

    @temp_created
    def write(self, db_label:str, variable:str, value:str) -> bool:
        """Write to temporary storage"""
        if self.read(db_label, variable) == value:
            log_aos.debug("[%s] Variable %s is already \"%s\"" % (db_label, variable, value))
            return True
        log_aos.debug("[%s] Write %s to %s" % (db_label, value, variable))
        return self.low_write(self.TEMP_IO_STREAMS[db_label], variable, value)

    def read(self, db_label:str, variable:str, default:str = None) -> str|None:
        """Read from temporary storage"""
        if not db_label in self.TEMP_IO_STREAMS:
            log_aos.debug("Label %s not in TEMP_IO_STREAMS" % db_label)
            return default
        value = self.low_read(self.TEMP_IO_STREAMS[db_label], variable)
        return value if value else default


""" Ace of States ubus service"""
Persistant_vault = AOS_Persistant()
Temporary_vault = AOS_Temporary()

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