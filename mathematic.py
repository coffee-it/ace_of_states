import logging

logger = logging.getLogger("Math")

class _Math():
    def transform_value(func):
        """ Декоратор, проверяет значения и трансформирует в int"""
        def banana_transform(db, variable, value):
            _old = db.read(variable=variable)
            _old = _old if _old != None else 0
            _old = int(_old) if str(_old).lstrip('-').isdigit() else 0
            _new = int(value) if str(value).lstrip('-').isdigit() else 0
            
            return func(db, variable, _new, old_value =_old)
            
        return banana_transform

    @staticmethod
    @transform_value
    def plus(db, variable, value:int, old_value:int=0):
        """ Прибавляет value к текущему значению variable """
        value = old_value + value
        return db.write(variable=variable, value=value)

    @staticmethod
    @transform_value
    def minus(db, variable, value:int, old_value:int=0):
        """ Вычитает value из текущего значения variable """
        value = old_value - value
        return db.write(variable=variable, value=value)

    @staticmethod
    @transform_value
    def add(db, variable, value:int, old_value:int=0):
        """
        Добавляет к variable изменение(разность м/у новым и текущим) value.
        Если новое значение меньше - прибавляем полностью.
        """
        if value < old_value:
            value = old_value + value
        else:
            value = old_value + (value - old_value)
        return db.write(variable=variable, value=value)

    @staticmethod
    @transform_value
    def extremum(db, variable, value:int, old_value:int=0):
        """
        Добавляет к variable разность м/у новым и текущим значением value
        если новое значение превышает текущее. В противном случае оставляем без изменений.
        """
        if value >= old_value:
            value = old_value + (value - old_value)
        else:
            logger.debug("Cant update extremum. Value of \"%s\" from \"%s\" is less then current" % (variable, db.VAULT))
            return False
        return db.write(variable=variable, value=value)

    @staticmethod
    @transform_value
    def collect(db, variable, value:int, old_value:int=0):
        """
        Собирает (коллекционирует) значение метрики, прибавляя дельту м/у старыми
        и новыми данными. Учитывает ситуации, когда собираемая метрика обнуляется и счёт начинается с нуля. 
        """
        adj_variable = 'adj_{}'.format(variable)
        adj_value = db.read(variable=adj_variable)
        adj_value = adj_value if adj_value != None else 0
        adj_value = int(adj_value) if str(adj_value).isdigit() else 0
        # adj_value уже получен, записываем новые данные
        db.write(variable=adj_variable, value=value)
        if value >= adj_value:
            # Собираемые данные равномерно растут, прибавляем дельту от новой и предыдущей метрики
            value = old_value + (value - adj_value)
            return db.write(variable=variable, value=value)
        elif value < adj_value:
            # Собираемый объект был обнулён, отсчёт начат сначала
            value += old_value
            return db.write(variable=variable, value=value)

class Math():
    def __init__(self, db) -> None:
        """
        Arguments:
            db - is AOS instance 
        """
        self.db = db

    def sub_instance(func):
        def sub(self, variable, value):
            return func(self.db, variable, value)

        return sub

    plus = sub_instance(_Math.plus)
    minus = sub_instance(_Math.minus)
    add = sub_instance(_Math.add)
    extremum = sub_instance(_Math.extremum)
    collect = sub_instance(_Math.collect)
