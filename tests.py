#!/usr/bin/micropython
import ace_of_states as aos

PERSISTANT_DB_PATH="/tmp/ace_of_states_tests"
ACE_Persistant = aos.Persistant()
ACE_Temporary = aos.Temporary()

""" Ace of States test cases"""
for ace in [ACE_Temporary, ACE_Persistant]:
    print("Test %s" % ace.__class__.__name__)
    assert ace.read('test_db', 'variable') == None, 'Variable not empty'
    assert ace.read('test_db', 'variable', 54) == 54, 'Default value is not returned'
    assert ace.write('test_db', 'variable', 0), 'Write is broken'
    assert ace.read('test_db', 'variable') == "0", 'Writen wrong value'
    ace.minus('test_db', 'variable', 5)
    assert ace.read('test_db', 'variable') == "-5", 'Bad decrement'
    ace.plus('test_db', 'variable', 10)
    assert ace.read('test_db', 'variable') == "5", 'Bad increment'
    ace.extremum('test_db', 'variable', 10)
    ace.extremum('test_db', 'variable', 42)
    ace.extremum('test_db', 'variable', 12)
    ace.extremum('test_db', 'variable', 5)
    assert ace.read('test_db', 'variable') == "42", 'Bad extremum'
    ace.collect('test_db', 'variable', 8)    # 50
    ace.collect('test_db', 'variable', 58)   # 100
    ace.collect('test_db', 'variable', 5)    # 105
    ace.collect('test_db', 'variable', 15)   # 115
    ace.collect('test_db', 'variable', 20)   # 120
    ace.collect('test_db', 'variable', 10)   # 130
    ace.collect('test_db', 'variable', 100)  # 220
    ace.collect('test_db', 'variable', 80)   # 300
    assert ace.read('test_db', 'variable') == "300", 'Is not 300. Relax.'
    ace.add('test_db', 'variable', 100)      # 400
    ace.add('test_db', 'variable', 666)      # 666
    ace.add('test_db', 'variable', 34)       # 700
    assert ace.read('test_db', 'variable') == "700", 'Bad add'