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



def run_on_each_clone(mg_id):

	all_clone_data = obj.get_given_parent_obj_info("storage", "clones")
	clone_dets = {clone['id']:clone['serial'] for clone in all_clone_data if clone['mediaGrpId'] == mg_id}
	for cid, cse in clone_dets.iteritems():
		print cid, cse

	clone_ids = obj._dict['mg_details'][mg]['clone_ids']
	for i in range(len(clone_ids)):
		cid = clone_ids[i]
		serial = clone_dets[cid]
		print "\n\nAssign->Connect->IO's->Disconn->UnAssing clone:%s\n"%serial
		if obj.assign_object('volumes', cid, ports, []):
			sys.exit(1)
	
		for ip in obj.port_ips:
			out, err = host_defs.execute_command('nvme connect -s 4420 -t rdma -a %s -n %s'%(ip, serial))
			if err:
				sys.exit(1)

		if arguments.fs_type and host_defs.create_mount_fs(arguments.fs_type):
			sys.exit(1)

		
		dets = host_defs.perform_ios('write', {})
		if not dets['pattern'] :
			sys.exit(1)

		if arguments.fail_over and  failover.trigger_fo(arguments, obj):
			sys.exit(1)
	
		dets = host_defs.perform_ios('read', dets)
		if not dets['pattern']:
			sys.exit(1)

		if arguments.fs_type and host_defs.umount_objs():
			sys.exit(1)

		if host_defs.disconnect_objs():
			sys.exit(1)

		if obj.unassign_object('volumes', cid):
			sys.exit(1)


		print"\n\n>>>>>>>>>>>>>>>>Completed for volume:%s<<<<<<<<<<<<<<<<<<\n\n"%str(i+1)


obj = target_defs.TARGET_API(arguments.conf_file)

if arguments.setup and obj.create_mg_vols():
	sys.exit(1)

if (not arguments.setup) and obj.get_details():
	sys.exit(1)

for i, mg in enumerate(obj._dict['mg_details'].keys(),1): 
	mg_id = obj._dict['mg_details'][mg]['mg_id']
	ports = obj._dict['mg_details'][mg]['ports']
	mg_sz = obj._dict['mg_details'][mg]['avail_size']
	mg_sz = int(mg_sz) * 48 / 100
	v_size= 100

	nvols = mg_sz / v_size
	obj.get_port_ips(ports)
	obj.port_ips = obj._dict['ipdetails'].values()
	#print obj.port_ips
	ports = [p.split(':')[1] for p in ports]		##Required

	print "\n>>>>Trying to create %s volumes of each %sG"%(str(nvols), str(v_size))
	nvols = 0
	for v in range(nvols):
		reservation = random.choice([90, 50, 10, 40, 20, 30, 70, 100, 60])
		vid = obj.create_volume(mg_id, str(v_size), 'vol_%s_%s'%(str(i),str(v)), reservation)
		if not vid:
			sys.exit(1)

		suffix = "m%s_v%s"%(str(i), str(v))
		sid = obj.create_copy(vid, 'snapshots', suffix)
		if not sid:
			sys.exit(1)

		cid = obj.create_copy(sid, 'clones', suffix)
		if not cid:
			sys.exit(1)

		print
	if obj.get_details():
		sys.exit(1)

	iters = arguments.iterations
	arguments.iterations = 1	##Overwriting for FailOver sequence to happen only once
	for i in range(int(iters)):
		if run_on_each_clone(mg_id):
			sys.exit(1)

		print "\n\tCompleted for iteration:%s\n"%str(i+1)

	###CLEANUP

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

