import wget,os
import argparse,subprocess
parser = argparse.ArgumentParser()
parser.add_argument("-n","--buildno",type=int, help="please type build no", required=True)
args = parser.parse_args()

ver = args.buildno
urlname = "http://172.25.28.72/release_archives_kernel/R1.5.1/latest/src_clientkit_centos_%s.tar.gz"%ver


def execute_command(command):
        print command
        proc = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return(proc.communicate())

## change directory
os.chdir("/tryit")
out,err = execute_command("rm -rf *")
wget.download(urlname)
out,err = execute_command(" tar -xvf s*")

# installing host drivers
out,err = execute_command("sh install.sh")
