#!/usr/bin/micropython
import logging, os
from micropython import const
from ace_of_states import AOS

__all__ = ['Persistant', 'Temporary']
PERSISTANT_DB_PATH=const("/opt/ace_of_states")

log_aos = logging.getLogger("AOS")

def os_exists(path):
    try:
        return os.stat(path)[0]
    except Exception as e:
        errno = e.args[0]
        if errno == errno.ENOENT:
            return 0
        raise e

class Ace_of_States_Basis():
    def __init__(self) -> None:
        self.TEMP_IO_STREAMS  = {}
        self.PERSISTANT_FILES = {}
        if not os_exists(PERSISTANT_DB_PATH):
            os.mkdir(PERSISTANT_DB_PATH)

    ###############################################################
    ### Temporary
    ###############################################################
    def temp_created(func):
        """Decorator which checks that the IO buffer is available"""
        def creation_checking(self, db_label, variable, value):
            if not db_label in self.TEMP_IO_STREAMS:
                log_aos.debug("[%s] Create btree IO instance" % db_label)
                self.TEMP_IO_STREAMS.update({db_label: AOS()})
            return func(self, db_label, variable, value)

        return creation_checking

    @temp_created
    def write(self, db_label:str, variable:str, value:str) -> bool:
        """Write to temporary storage"""
        if self.read(db_label, variable) == value:
            log_aos.debug("[%s] Variable \"%s\" is already \"%s\"" % (db_label, variable, value))
            return True
        log_aos.debug("[%s] Write \"%s\" to \"%s\"" % (db_label, value, variable))
        return self.TEMP_IO_STREAMS[db_label].write(variable, value)

    def read(self, db_label:str, variable:str, default:str = None) -> str|None:
        """Read from temporary storage"""
        if not db_label in self.TEMP_IO_STREAMS:
            log_aos.debug("Label \"%s\" not in TEMP_IO_STREAMS" % db_label)
            return default
        value = self.TEMP_IO_STREAMS[db_label].read(variable)
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

class Persistant(Ace_of_States_Basis):
    def persistant_created(func):
        """Decorator which checks that the DB file is available"""
        def creation_checking(self, db_label, variable, value):
            if not db_label in self.PERSISTANT_FILES:
                if not os_exists("%s/%s" % (PERSISTANT_DB_PATH, db_label)):
                    log_aos.debug("[%s] Create btree IO instance" % db_label)
                _aos_node = AOS("/".join((PERSISTANT_DB_PATH, db_label)))
                _aos_node.register_sync()
                self.PERSISTANT_FILES.update({db_label: _aos_node})
            return func(self, db_label, variable, value)

        return creation_checking

    @persistant_created
    def write(self, db_label, variable, value) -> bool:
        """Write to persistant storage"""
        if self.read(db_label, variable) == value:
            log_aos.debug("[%s] Variable \"%s\" is already \"%s\"" % (db_label, variable, value))
            return True
        log_aos.debug("[%s] Write \"%s\" to \"%s\"" % (db_label, value, variable))
        return self.PERSISTANT_FILES[db_label].write(variable, value)

    def read(self, db_label:str, variable:str, default:str = None) -> str|None:
        """Read from persistant storage"""
        if not db_label in self.PERSISTANT_FILES:
            if os_exists("/".join((PERSISTANT_DB_PATH, db_label))):
                self.PERSISTANT_FILES.update({db_label: AOS("/".join((PERSISTANT_DB_PATH, db_label)))})
            else:
                log_aos.debug("Label \"%s\" not in PERSISTANT_FILES" % db_label)
                return default
        value = self.PERSISTANT_FILES[db_label].read(variable)
        return value if value else default
    
    def sync(self, db_label:str):
        if db_label in self.PERSISTANT_FILES:
            self.PERSISTANT_FILES[db_label].sync()
class Temporary(Ace_of_States_Basis):
    pass