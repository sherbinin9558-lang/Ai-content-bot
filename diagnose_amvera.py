import os, sys
print('CWD=', os.getcwd())
print('ROOT=', os.listdir('.'))
print('APP=', os.listdir('/app') if os.path.isdir('/app') else 'NO_APP')
print('SYS_PATH=', sys.path)
