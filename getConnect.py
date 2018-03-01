import paramiko
import subprocess

class helper_func:
    def __init__(self,port=None):
        self.port = 22
    
    def sshConn(self,hostname,user,passwd):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            print("Creating connection")
            ssh.connect(hostname,self.port,user,passwd)
            return(ssh)
        except Exception as e:
            print("Connection failed")
            print("ERROR:",e)

    def run_command(self,sshobj,cmd):
        print(cmd)
        proc = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return(proc.communicate())
       


if __name__=='__main__':
    obj = helper_func()
    mgmt_sshObj = obj.sshConn("172.25.26.9","root","2bon2b")
    #run command on mgmt
    op,err = obj.run_command(mgmt_sshObj,"ls")
    print op 
