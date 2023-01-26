#!/usr/bin/micropython
from ace_of_states import AOS, os_exists
import uos

PERSISTANT_DB_PATH="/tmp/ace_of_states_tests"
if not os_exists(PERSISTANT_DB_PATH):
    uos.mkdir(PERSISTANT_DB_PATH)
AOS_Persistant = AOS("/".join((PERSISTANT_DB_PATH, "test_db")))
AOS_Temporary = AOS()

""" Ace of States test cases"""
for ace in [AOS_Temporary, AOS_Persistant]:
    print("Test %s" % ace.__class__.__name__)
    with ace as db:
        assert db.read('variable') == None, 'Variable not empty'
        assert db.read('variable', 54) == 54, 'Default value is not returned'
        assert db.write('variable', 0), 'Write is broken'
        assert db.read('variable') == "0", 'Writen wrong value'
        db.minus('variable', 5)
        assert db.read('variable') == "-5", 'Bad decrement'
        db.plus('variable', 10)
        assert db.read('variable') == "5", 'Bad increment'
        db.extremum('variable', 10)
        db.extremum('variable', 42)
        db.extremum('variable', 12)
        db.extremum('variable', 5)
        assert db.read('variable') == "42", 'Bad extremum'
        db.collect('variable', 8)    # 50
        db.collect('variable', 58)   # 100
        db.collect('variable', 5)    # 105
        db.collect('variable', 15)   # 115
        db.collect('variable', 20)   # 120
        db.collect('variable', 10)   # 130
        db.collect('variable', 100)  # 220
        db.collect('variable', 80)   # 300
        assert db.read('variable') == "300", 'Bad collect. Is not 300 You dodged, this time'
        db.add('variable', 100)      # 400
        db.add('variable', 666)      # 666
        db.add('variable', 34)       # 700
        assert db.read('variable') == "700", 'Bad add'

uos.remove("/".join((PERSISTANT_DB_PATH, "test_db")))
uos.rmdir(PERSISTANT_DB_PATH)
print("Test complete")