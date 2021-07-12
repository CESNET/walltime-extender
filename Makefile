include /etc/pbs.conf

CFLAGS = -Wall -Wno-unused-variable -fPIC -shared -I${PBS_EXEC}/include -I/usr/include/python3.7 -L${PBS_EXEC}/lib
LDLIBS = -lpbs
CC = gcc

all: swig pbs_ifl.so
	export LD_LIBRARY_PATH=${PBS_EXEC}/lib:${LD_LIBRARY_PATH}
	ldd ./_pbs_ifl.so

swig:
	swig -python -I${PBS_EXEC}/include ./pbs_ifl.i

pbs_ifl.so: pbs_ifl.py pbs_ifl_wrap.c
	$(CC) $(CFLAGS) $(LDLIBS) -o _pbs_ifl.so ./pbs_ifl_wrap.c

clean:
	$(RM) -r __pycache__ _pbs_ifl.so pbs_ifl.py pbs_ifl.pyc pbs_ifl_wrap.c 
