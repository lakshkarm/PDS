import argparse, sys, random
import host_defs, target_defs, failover


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

parser.add_argument('-o', action='store_true', default=False, dest='fail_over',
                    help='Starts FailOver Sequences')

parser.add_argument('-r', action='store_true', default=False, dest='rand',
                    help='Random flag')

parser.add_argument('-x', action='store_true', default=False, dest='setup',
                    help='Target side setup')

arguments = parser.parse_args()
print arguments

def validate_on_copy(copy_type, pid, suffix, dets):
	print "\n>>>>Creating %s, assigning & connect"%copy_type
	_id = obj.create_copy(pid, copy_type, suffix)
	if not _id:
		return None

	if assign_connect(_id, ports):
		return None

	if arguments.fail_over and failover.trigger_fo(arguments, obj):
		sys.exit(1)

	_tmp = host_defs.perform_ios('read', dets)
	if not _tmp['pattern']:
		return(1)

	print ">>>>Completed reads, unmount, unassign.." 

	if disconnect_unassign(_id):
		return None

	return(_id)


def assign_connect(objid, ports):
	if obj.assign_object('volumes', objid, ports, []):
		return(1)
	
	if host_defs.connect_volumes(obj.port_ips):
		return(1)

	return(0)


def disconnect_unassign(objid):
	if arguments.fs_type and host_defs.umount_objs():
		return(1)

	if host_defs.disconnect_objs():
		return(1)

	if obj.unassign_object('volumes', objid):
		return(1)


	return(0)


obj = target_defs.TARGET_API(arguments.conf_file)

if arguments.setup and obj.create_mg_vols():
	sys.exit(1)

elif obj.get_details():
	sys.exit(1)

for i, mg in enumerate(obj._dict['mg_details'].keys(),1): 
	mg_id = obj._dict['mg_details'][mg]['mg_id']
	ports = obj._dict['mg_details'][mg]['ports']
	mg_sz = obj._dict['mg_details'][mg]['avail_size']
	mg_sz = int(mg_sz) * 48 / 100

	nvols = mg_sz / 100
	obj.get_port_ips(ports)
	obj.port_ips = obj._dict['ipdetails'].values()
	#print obj.port_ips
	ports = [p.split(':')[1] for p in ports]		##Required

	print "\n>>>>Trying to create %s volumes of each 100G"%(str(nvols))
	for v in range(nvols):
		reservation = random.choice([90, 50, 10, 40, 20, 30, 70, 100, 60])
		vid = obj.create_volume(mg_id, 100, 'vol_%s_%s'%(str(i),str(v)), reservation)
		if not vid:
			sys.exit(1)

		if assign_connect(vid, ports):
			sys.exit(1)

		if arguments.fs_type and host_defs.create_mount_fs(arguments.fs_type):
			sys.exit(1)
	
		dets = host_defs.perform_ios('write', {})
		if not dets['pattern'] :
			sys.exit(1)

		if arguments.fail_over and failover.trigger_fo(arguments, obj):
			sys.exit(1)
	
		dets = host_defs.perform_ios('read', dets)
		if not dets['pattern']:
			sys.exit(1)

		if disconnect_unassign(vid):
			sys.exit(1)

		suffix = "m%s_v%s"%(str(i), str(v))

		sid = validate_on_copy('snapshots', vid, suffix, dets)
		if not sid:
			sys.exit(1)

		cid = validate_on_copy('clones', sid, suffix, dets)
		if not cid:
			sys.exit(1)

		print "\n<><><><><><><><><><Completed for volume :%s><><><><><><><><><><><><><>\n\n"%(str(v))

	if obj.get_details():
		sys.exit(1)

	if arguments.fs_type and host_defs.umount_objs():
		sys.exit(1)

	data = {}
	api = "https://"+obj._dict['ip']+"/api/v1.0/storage/snapshots/delete"
	data["snapshotidlist"] = obj._dict['mg_details'][mg]['clone_ids']
	print "\n>>>>Deleting Clones..."
	st, text = obj.run_api(api, data, 'POST')
	if st == -1:
		sys.exit(1)

	print "\n>>>>Deleting Snapshots..."
	data["snapshotidlist"] = obj._dict['mg_details'][mg]['snap_ids']
	st, text = obj.run_api(api, data, 'POST')
	if st == -1:
		sys.exit(1)

	print "\n>>>>Deleting Volumes..."
	data = {}
	api = "https://"+obj._dict['ip']+"/api/v1.0/storage/volumes/delete"
	data["volidlist"] = obj._dict['mg_details'][mg]['vol_ids']
	st, text = obj.run_api(api, data, 'POST')
	if st == -1:
		sys.exit(1)

	if obj.del_media_group([mg]):
		sys.exit(1)

	sys.exit(0)

