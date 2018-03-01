import logging ,paramiko,multiprocessing
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)-8s %(message)s',
                    datefmt='%a, %d %b %Y %H:%M:%S',
                    filename='myapp.log')

#console = logging.StreamHandler()
#console.setLevel(logging.INFO)

logger.info("hello")

def sshConn(hostname,user,passwd,port=22):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print("Creating connection")
        ssh.connect(hostname,port,user,passwd)
        stdout,stderr = ssh.exec_command("ls")
        print(stdout)
        return(ssh)
    except Exception as e:
        print("Connection failed")
        print("ERROR:",e)

def run_command(sshobj,cmd):
    print(cmd)
    proc = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return(proc.communicate())

def switch_system():
    pass


def add(a=4,b=None):
    if a and b:
        sum = a+b
        print(sum) 
    else:
        sum = a + a
        print(sum )

def sub(a,b,m=None):
    if m:
        print "pass"
    else:
        sub = a - b
        print sub


if __name__=='__main__':
    #sshConn("172.25.26.9",'admin','admin')
     add(5,12)
   
     p = multiprocessing.Process(target=add, args=(1,3))
     p.start()
     sub(7,1)
     a = 12323
     logger.info("this is %s"%a)
    #print [x for x in range(1,20) if x%2==0 ] 
    #print [x for x in 'MATHEMATICS' if x in ['A','E','I','O','U']]
