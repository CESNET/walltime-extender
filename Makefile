include /etc/pbs.conf

CFLAGS = -Wall -Wno-unused-variable -fPIC -shared -I${PBS_EXEC}/include -I/usr/include/python3.11 -I/usr/include/python3.7 -I/usr/include/python3.6m -L${PBS_EXEC}/lib
LDLIBS = -lpbs -lcrypto -lssl
CC = gcc

all: swig pbs_ifl.so
	ldd ./_pbs_ifl.so

swig:
	swig -python -I${PBS_EXEC}/include ./pbs_ifl.i

pbs_ifl.so: pbs_ifl.py pbs_ifl_wrap.c
	$(CC) $(CFLAGS) $(LDLIBS) -o _pbs_ifl.so ./pbs_ifl_wrap.c $(LDLIBS) 

clean:
	$(RM) -r __pycache__ _pbs_ifl.so pbs_ifl.py pbs_ifl.pyc pbs_ifl_wrap.c 
