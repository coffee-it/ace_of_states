import logging

logger = logging.getLogger("Math")

class _Math():

    @staticmethod
    def plus(value:int, old_value:int=0):
        """ Возвращает сумму старого и нового значения value """
        return old_value + value

    @staticmethod
    def minus(value:int, old_value:int=0):
        """ Возвращает разницу м/у старым и новым значением value """
        return old_value - value

    @staticmethod
    def add(value:int, old_value:int=0):
        """
        Возвращает изменение(разность м/у новым и текущим) value.\n
        Если новое значение меньше - прибавляем полностью.
        """
        if value < old_value:
            return old_value + value
        else:
            return old_value + (value - old_value)

    @staticmethod
    def extremum(value:int, old_value:int=0):
        """
        Возвращает value для записи если оно выше old_value
        """
        if value >= old_value:
            return old_value + (value - old_value)
        else:
            return None

    @staticmethod
    def collect(value:int, old_value:int=0, adj_value:int=0):
        """
        Возвращает новое значение value\n
        collect(value, old_value, adj_value)\n
            - value: новое значение переменной\n
            - old_value: предыдущее значение переменной\n
            - adj_value: сравниваемое значение из хранилища\n
        В родительской функции необходимо обеспечить сохранение adj_value
        """
        if value >= adj_value:
            # Собираемые данные равномерно растут, прибавляем дельту от новой и предыдущей метрики
            return old_value + (value - adj_value)
        elif value < adj_value:
            # Собираемый объект был обнулён, отсчёт начат сначала
            value += old_value
            return value

class Math():
    def __init__(self, db) -> None:
        """
        Arguments:
            db - is AOS instance 
        """
        self.db = db

    def transform_value(func):
        """ Декоратор, проверяет значения и трансформирует в int"""
        def banana_transform(self, variable, value):
            _old = self.db.read(variable=variable)
            _old = _old if _old != None else 0
            _old = int(_old) if str(_old).lstrip('-').isdigit() else 0
            _new = int(value) if str(value).lstrip('-').isdigit() else 0
            
            return func(self, variable, _new, old_value =_old)

        return banana_transform

    @transform_value
    def plus(self, variable, value:int, old_value:int=0):
        """ Прибавляет value к текущему значению variable """
        return self.db.write(variable=variable, value=_Math.plus(value, old_value))

    @transform_value
    def minus(self, variable, value:int, old_value:int=0):
        """ Вычитает value из текущего значения variable """
        return self.db.write(variable=variable, value=_Math.minus(value, old_value))

    @transform_value
    def add(self, variable, value:int, old_value:int=0):
        """
        Добавляет к variable изменение(разность м/у новым и текущим) value.
        Если новое значение меньше - прибавляем полностью.
        """
        return self.db.write(variable=variable, value=_Math.add(value, old_value))

    @transform_value
    def extremum(self, variable, value:int, old_value:int=0):
        """
        Добавляет к variable разность м/у новым и текущим значением value\n
        если новое значение превышает текущее. В противном случае оставляем без изменений.
        """
        value = _Math.extremum(value, old_value)
        if value:
            return self.db.write(variable=variable, value=value)
        logger.debug("Cant update extremum. Value of \"%s\" from \"%s\" is less then current" % (variable, self.db.VAULT))

    @transform_value
    def collect(self, variable, value:int, old_value:int=0):
        """
        Собирает (коллекционирует) значение метрики, прибавляя дельту м/у старыми\n
        и новыми данными. Учитывает ситуации, когда собираемая метрика обнуляется и счёт начинается с нуля. 
        """
        adj_variable = 'adj_{}'.format(variable)
        adj_value = self.db.read(variable=adj_variable)
        adj_value = adj_value if adj_value != None else 0
        adj_value = int(adj_value) if str(adj_value).isdigit() else 0
        # adj_value уже получен, записываем новые данные
        self.db.write(variable=adj_variable, value=value)

        return self.db.write(variable=variable, value=_Math.collect(value, old_value, adj_value))

