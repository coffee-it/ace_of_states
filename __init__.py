#!/usr/bin/micropython
import uio, btree, logging
from functools import partial
from os import path, stat
from atsignal import SignalHandler
from usys import atexit
from ace_of_states.mathematic import Math
import errno

log_aos = logging.getLogger("AOS")

class DirNotFoundError(BaseException):
    pass

class AceError(BaseException):
    pass

def os_exists(path):
    try:
        return stat(path)[0]
    except Exception as e:
        if e.args[0] == errno.ENOENT:
            return 0
        raise e

class Ace():
    @staticmethod
    def get_db_fd(absolut_path):
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

    @staticmethod
    def low_dump(btreeIO):
        return btreeIO.items()

    def low_delete(btreeIO, variable: str) -> bool:
        if not getattr(btreeIO, 'get', False): raise AceError("btreeIO closed")
        try:
            del btreeIO[str(variable)]
            return True
        except KeyError:
            return True

class AOS():
    def __init__(self, file = None) -> None:
        self.VAULT = None
        self.fd = None
        self.Math = Math(self)
        if file:
            self.fd = Ace.get_db_fd(file)
            if not self.fd:
                log_aos.error("No such file or direcory: %s" % file)
                raise DirNotFoundError("No such file or direcory: %s" % file)
            self.VAULT = btree.open(Ace.get_db_fd(file))
        else:
            self.VAULT = btree.open(uio.BytesIO())

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.sync()

    def dump(self):
        """ Return all variable-value pairs """
        return Ace.low_dump(self.VAULT)

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
        """ Read value from db
            Arguments:
                - variable - is a db key
                - default  - value that returns if variable value is empty or None 

            Return value or default if value is empty or None
        """
        value = Ace.low_read(self.VAULT, variable)
        return value if value else default
    
    def delete(self, variable: str) -> bool:
        """ Delete key from db
            Arguments:
                - variable - is a db key

            Return True
        """
        return Ace.low_delete(self.VAULT, variable)

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
