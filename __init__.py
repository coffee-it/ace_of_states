#!/usr/bin/micropython
import uio, btree, logging
from functools import partial
from os import path, stat
from atsignal import SignalHandler
from usys import atexit

log_aos = logging.getLogger("AOS")

class DirNotFoundError(BaseException):
    pass

class AceError(BaseException):
    pass

def os_exists(path):
    try:
        return stat(path)[0]
    except Exception as e:
        errno = e.args[0]
        if errno == errno.ENOENT:
            return 0
        raise e

class Ace():
    @staticmethod
    def open_db_from_file(absolut_path):
        _dir=path.dirname(absolut_path)
        if not path.isdir(_dir):
            log_aos.error("No such file or direcory: %s" % _dir)
            return None
        try:
            f = open(absolut_path, 'r+b')
        except:
            f = open(absolut_path, 'w+b')
        return f

    @staticmethod
    def sync(btreeIO) -> None:
        btreeIO.flush()
        log_aos.debug("Sync %s to underlaying stream" % btreeIO)

    @staticmethod
    def low_write(btreeIO, variable: str, value: str) -> bool:
        if not getattr(btreeIO, 'put', False): raise AceError("btreeIO closed")
        try:
            btreeIO.put(variable, str(value))
        except Exception as e:
            log_aos.error("Low write error [%s, %s]" % (variable, value))
            log_aos.debug("%s" % e)
            return False
        else:
            return True

    @staticmethod
    def low_read(btreeIO, variable: str) -> str|None:
        if not getattr(btreeIO, 'get', False): raise AceError("btreeIO closed")
        value = btreeIO.get(str(variable))
        if value: return value.decode('utf-8')
        return None

class AOS():
    def __init__(self, file = None) -> None:
        self.VAULT = None
        self.fd = None
        if file:
            self.fd = Ace.open_db_from_file(file)
            if not fd:
                log_aos.error("No such file or direcory: %s" % file)
                raise DirNotFoundError("No such file or direcory: %s" % file)
            self.VAULT = btree.open(Ace.open_db_from_file(file))
        else:
            self.VAULT = btree.open(uio.BytesIO())

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.sync()

    def register_sync(self):
        """ Register the execution of sync() method after receiving the SIGINT,SIGTERM signal or exit"""
        SignalHandler.register(2, Ace.sync, self.VAULT)
        SignalHandler.register(15, Ace.sync, self.VAULT)
        atexit(partial(Ace.sync, self.VAULT))
        log_aos.debug("Register sync at exit")

    def write(self, variable: str, value) -> bool:
        """ Write value to db
            Arguments:
                - variable - is a db key
                - value

            Return writing result as True or False
        """
        return Ace.low_write(self.VAULT, variable, value)

    def read(self, variable: str, default: str = None) -> str|None:
        """ Read value from db key
            Arguments:
                - variable - is a db key
                - value

            Return value or default if empty or None
        """
        value = Ace.low_read(self.VAULT, variable)
        return value if value else default

    def save_type(self, variable: str, value) -> bool:
        """ Save variable type
            Arguments:
                - variable - variable name from db
                - value    - the value whose type will be stored

        Return True or False
        """
        datatype = type(value)
        if datatype not in (int, float, str, dict, list, set, tuple, bytes):
            log_aos.error("Datatype must be one of int, float, str, dict, list, set, tuple, bytes")
            return False
            # raise AceError("Datatype must be one of int, float, str, dict, list, set, tuple, bytes")
        if hasattr(datatype, "__name__"):
            datatype = getattr(datatype, "__name__")
        Ace.low_write(self.VAULT, "_%s_type" % variable, datatype)

    def restore_type(self, variable: str, value: str) -> int|float|str|dict|list|set|tuple|bytes:
        """ Restore variable type
            Arguments:
                - variable - variable name from db
                - value    - the value of the variable whose type is to be resored

        Return typed or original value
        """
        datatype = Ace.low_read(self.VAULT, "_%s_type" % variable)
        if datatype:
            datatype = eval(datatype)
            value = datatype(eval(value))
        else:
            log_aos.error("No saving datatype for variable %s" % variable)
        return value

    def sync(self):
        """ Sync DB to underlaying stream"""
        Ace.sync(self.VAULT)

    def close(self):
        """ Sync DB to underlaying stream, close db instance and fd"""
        self.sync()
        self.VAULT = None

    ###############################################################
    ### Math
    ###############################################################
    def transform_value(func):
        """ Декоратор, проверяет значения и трансформирует в int"""
        def banana_transform(self, variable, value):
            _old = self.read(variable=variable)
            _old = _old if _old != None else 0
            _old = int(_old) if str(_old).lstrip('-').isdigit() else 0
            _new = int(value) if str(value).lstrip('-').isdigit() else 0
            
            return func(self, variable, _new, old_value =_old)
            
        return banana_transform
    @transform_value
    def plus(self, variable, value:int, old_value:int=0):
        """ Прибавляет value к текущему значению variable """
        value = old_value + value
        self.write(variable=variable, value=value)
    @transform_value
    def minus(self, variable, value:int, old_value:int=0):
        """ Вычитает value из текущего значения variable """
        value = old_value - value
        self.write(variable=variable, value=value)

    @transform_value
    def add(self, variable, value:int, old_value:int=0):
        """
        Добавляет к variable изменение(разность м/у новым и текущим) value.
        Если новое значение меньше - прибавляем полностью.
        """
        if value < old_value:
            value = old_value + value
        else:
            value = old_value + (value - old_value)
        self.write(variable=variable, value=value)

    @transform_value
    def extremum(self, variable, value:int, old_value:int=0):
        """
        Добавляет к variable разность м/у новым и текущим значением value
        если новое значение превышает текущее. В противном случае оставляем без изменений.
        """
        if value >= old_value:
            value = old_value + (value - old_value)
        else:
            log_aos.debug("Cant update extremum. Value of \"%s\" from \"%s\" is less then current" % (variable, self.VAULT))
            return False
        self.write(variable=variable, value=value)

    @transform_value
    def collect(self, variable, value:int, old_value:int=0):
        """
        Собирает (коллекционирует) значение метрики, прибавляя дельту м/у старыми
        и новыми данными. Учитывает ситуации, когда собираемая метрика обнуляется и счёт начинается с нуля. 
        """
        adj_variable = 'adj_{}'.format(variable)
        adj_value = self.read(variable=adj_variable)
        adj_value = adj_value if adj_value != None else 0
        adj_value = int(adj_value) if str(adj_value).isdigit() else 0
        # adj_value уже получен, записываем новые данные
        self.write(variable=adj_variable, value=value)
        if value >= adj_value:
            # Собираемые данные равномерно растут, прибавляем дельту от новой и предыдущей метрики
            value = old_value + (value - adj_value)
            self.write(variable=variable, value=value)
        elif value < adj_value:
            # Собираемый объект был обнулён, отсчёт начат сначала
            value += old_value
            self.write(variable=variable, value=value)
