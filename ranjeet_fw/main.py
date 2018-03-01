import argparse, sys, time, multiprocessing, datetime
import host_defs, target_defs, failover, parallel


##MAIN
parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument('-s', action='store', dest='interval', default=0,
                    help='Interval between flipflap')

parser.add_argument('-i', action='store', dest='iterations', default=0,
                    help='Number of iterations')

parser.add_argument('-f', action='store', dest='fs_type', default=None,
                    help='FileSystem to be used for formatting objects')

parser.add_argument('-t', action='store', default=None, dest='conf_file',
                    help='Enables script to do target operations based on conf file')

parser.add_argument('-l', action='store', dest='lvm', default=0,
                    help='Creates LVM on detected devices')

parser.add_argument('-p', action='store', default=None, dest='parallel',
                    help='Parallel ops will be initiated. Ex: drives|objects')

parser.add_argument('-o', action='store_true', default=False, dest='fail_over',
                    help='Starts FailOver Sequences')

parser.add_argument('-r', action='store_true', default=False, dest='rand',
                    help='Random flag')

parser.add_argument('-x', action='store_true', default=False, dest='setup',
                    help='Target side setup')

parser.add_argument('-y', action='store_true', default=False, dest='cleanup',
                    help='Cleanups host/target side')

parser.add_argument('-z', action='store_true', default=False, dest='ios_enabled',
                    help='Start IO')


arguments = parser.parse_args()
print arguments

if not arguments.conf_file:
	print "ERROR! Pls provide config file"
	sys.exit(1)

_api = target_defs.TARGET_API(arguments.conf_file)

if arguments.setup:
	if _api.setup() or host_defs.connect_volumes(_api.port_ips):
		sys.exit(1)
else:
	if _api.get_details():
		sys.exit(1)

if int(arguments.lvm) and host_defs.linux_lvm(int(arguments.lvm)):
	sys.exit(1)

if arguments.fs_type and host_defs.create_mount_fs(arguments.fs_type):
	sys.exit(1)


if arguments.ios_enabled:
	job, log = host_defs.get_io_jobfile(arguments.fs_type)
	print job, log, "\n"
	sys.exit(0)

	print "\nStarting IO in BG"
	io_t = multiprocessing.Process(target=host_defs.run_io_job, args=(job, log))
	io_d.daemon = True
	io_t.start()
	time.sleep(30)

if arguments.parallel:
	if parallel.multiple_ops(_api, arguments): 
		sys.exit(1)

if arguments.fail_over :
	st = failover.trigger_fo(arguments, _api)
	if arguments.ios_enabled:
		io_t.terminate()
		io_t.join()
		st = host_defs.verify_io_log(log) | st
	if arguments.parallel:
		po_t.terminate()
		po_t.join()
		st =  parallel.check_failure(_api.parallel_ops_log) | st
	if st :
		print "ERROR! Failure noticed"
		sys.exit(1)
	
if arguments.ios_enabled:
	print "\nWaiting for IO Job to complete.."
	print "is_alive()", io_t.is_alive()
	io_t.is_alive() | io_t.join()

	if host_defs.verify_io_log(log):
		sys.exit(1)


##CLEANUP
if arguments.cleanup:
	if host_defs.cleanup(arguments.lvm, arguments.fs_type):
		sys.exit(1)
	
	if _api.cleanup():
		sys.exit(1)



sys.exit(0)
