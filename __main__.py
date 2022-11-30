from sys import argv, stdin
if len(argv) == 1:
    print("No one argument given, read stdin insted")
    for _in in stdin:
        argv.append(_in)

print(argv)
import ananas
print(ananas.persistant_db)