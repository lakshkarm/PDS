import argparse
parser = argparse.ArgumentParser()
parser.add_argument("echo", help="echo the string you use here")
args = parser.parse_args()
print args.echo


def add(a=None):
    if a == 0:
        print "hello"
    else:
        print "valuen is not defines"

add(0)
