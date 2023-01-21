#!/usr/bin/micropython
import uio, btree, logging, os, errno
from atsignal import SignalHandler
from micropython import const

__all__ = ['AOS_Persistant', 'AOS_Temporary']
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
        SignalHandler.register(2, self._sync_all_persistant)
        SignalHandler.register(15, self._sync_all_persistant)

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
    def sync(self, btreeIO) -> None:
        btreeIO.flush()
        log_aos.debug("Sync IO %s" % btreeIO)
    def _sync_all_persistant(self) -> None:
        for f in self.PERSISTANT_FILES:
            self.sync(self.PERSISTANT_FILES[f])

    ###############################################################
    ### Temporary
    ###############################################################
    def temp_created(func):
        """Decorator which checks that the IO buffer is available"""
        def creation_checking(self, db_label, variable, value):
            if not db_label is self.VAULT:
                if not db_label in self.TEMP_IO_STREAMS:
                    log_aos.debug("[%s] Create btree IO instance" % db_label)
                    self.TEMP_IO_STREAMS.update({db_label: btree.open(uio.BytesIO())})
            return func(self, db_label, variable, value)

        return creation_checking

    @temp_created
    def write(self, db_label:str, variable:str, value:str) -> bool:
        """Write to temporary storage"""
        if self.read(db_label, variable) == value:
            log_aos.debug("[%s] Variable \"%s\" is already \"%s\"" % (db_label, variable, value))
            return True
        if db_label is self.VAULT:
            log_aos.debug("[%s] Write \"%s\" to \"%s\"" % ("VAULT", value, variable))
            return self.low_write(db_label, variable, value)
        else:
            log_aos.debug("[%s] Write \"%s\" to \"%s\"" % (db_label, value, variable))
            return self.low_write(self.TEMP_IO_STREAMS[db_label], variable, value)

    def read(self, db_label:str, variable:str, default:str = None) -> str|None:
        """Read from temporary storage"""
        if db_label is self.VAULT:
            value = self.low_read(db_label, variable)
        else:
            if not db_label in self.TEMP_IO_STREAMS:
                log_aos.debug("Label \"%s\" not in TEMP_IO_STREAMS" % db_label)
                return default
            value = self.low_read(self.TEMP_IO_STREAMS[db_label], variable)
        return value if value else default

    ###############################################################
    ### Math
    ###############################################################
    def transform_value(func):
        """ Декоратор, проверяет значения и трансформирует в int"""
        def banana_transform(self, db_label, variable, value):
            _old = self.read(db_label=db_label, variable=variable)
            _old = _old if _old != None else 0
            _old = int(_old) if str(_old).lstrip('-').isdigit() else 0
            _new = int(value) if str(value).lstrip('-').isdigit() else 0
            
            return func(self, db_label, variable, _new, old_value=_old)
            
        return banana_transform
    @transform_value
    def plus(self, db_label, variable, value:int, old_value:int=0):
        """ Прибавляет value к текущему значению variable """
        value = old_value + value
        self.write(db_label=db_label, variable=variable, value=value)
    @transform_value
    def minus(self, db_label, variable, value:int, old_value:int=0):
        """ Вычитает value из текущего значения variable """
        value = old_value - value
        self.write(db_label=db_label, variable=variable, value=value)

    @transform_value
    def add(self, db_label, variable, value:int, old_value:int=0):
        """
        Добавляет к variable изменение(разность м/у новым и текущим) value.
        Если новое значение меньше - прибавляем полностью.
        """
        if value < old_value:
            value = old_value + value
        else:
            value = old_value + (value - old_value)
        self.write(db_label=db_label, variable=variable, value=value)

    @transform_value
    def extremum(self, db_label, variable, value:int, old_value:int=0):
        """
        Добавляет к variable разность м/у новым и текущим значением value
        если новое значение превышает текущее. В противном случае оставляем без изменений.
        """
        if value >= old_value:
            value = old_value + (value - old_value)
        else:
            log_aos.debug("Cant update extremum. Value of \"%s\" from \"%s\" is less then current" % (variable, db_label))
            return False
        self.write(db_label=db_label, variable=variable, value=value)

    @transform_value
    def collect(self, db_label, variable, value:int, old_value:int=0):
        """
        Собирает (коллекционирует) значение метрики, прибавляя дельту м/у старыми
        и новыми данными. Учитывает ситуации, когда собираемая метрика обнуляется и счёт начинается с нуля. 
        """
        adj_variable = 'adj_{}'.format(variable)
        adj_value = self.read(db_label=db_label, variable=adj_variable)
        adj_value = adj_value if adj_value != None else 0
        adj_value = int(adj_value) if str(adj_value).isdigit() else 0
        # adj_value уже получен, записываем новые данные
        self.write(db_label=db_label, variable=adj_variable, value=value)
        if value >= adj_value:
            # Собираемые данные равномерно растут, прибавляем дельту от новой и предыдущей метрики
            value = old_value + (value - adj_value)
            self.write(db_label=db_label, variable=variable, value=value)
        elif value < adj_value:
            # Собираемый объект был обнулён, отсчёт начат сначала
            value += old_value
            self.write(db_label=db_label, variable=variable, value=value)

    ###############################################################
    ### Other
    ###############################################################
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

class Persistant(Ace_of_States_Basis):
    def persistant_created(func):
        """Decorator which checks that the DB file is available"""
        def creation_checking(self, db_label, variable, value):
            if not db_label is self.VAULT:
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
            log_aos.debug("[%s] Variable \"%s\" is already \"%s\"" % (db_label, variable, value))
            return True
        if db_label is self.VAULT:
            log_aos.debug("[%s] Write \"%s\" to \"%s\"" % ("VAULT", value, variable))
            return self.low_write(db_label, variable, value)
        else:
            log_aos.debug("[%s] Write \"%s\" to \"%s\"" % (db_label, value, variable))
            return self.low_write(self.PERSISTANT_FILES[db_label], variable, value)

    def read(self, db_label:str, variable:str, default:str = None) -> str|None:
        """Read from persistant storage"""
        if db_label is self.VAULT:
            value = self.low_read(db_label, variable)
        else:
            if not db_label in self.PERSISTANT_FILES:
                # but
                if os_exists("%s/%s" % (PERSISTANT_DB_PATH, db_label)):
                    self.PERSISTANT_FILES.update({db_label: btree.open(self.open_db_from_file("%s/%s" % (PERSISTANT_DB_PATH, db_label)))})
                else:
                    log_aos.debug("Label \"%s\" not in PERSISTANT_FILES" % db_label)
                    return default
            value = self.low_read(self.PERSISTANT_FILES[db_label], variable)
        return value if value else default

class Temporary(Ace_of_States_Basis):
    pass