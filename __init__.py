import uio, btree

# File DB storage
try:
    f = open('/opt/aceos.db', 'r+b')
except:
    f = open('/opt/aceos.db', 'w+b')

# in-Memory storage
zz = uio.BytesIO()


persistant_db = btree.open(f)