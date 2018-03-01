import subprocess, sys, os, time, random
import target_defs

def execute_command(command):
	print command
	proc = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	return(proc.communicate())


def multiple_ops(obj, options):

	if options.parallel == 'objects':
		return(objects_create_delete(obj, options))

	elif options.parallel == 'drives':
		return(drives_powercycle(obj, options))



def objects_create_delete(obj, options):
	print "Performing parallel operations on MG..."
	
	for i, mg in enumerate(obj._dict['mg_details'].keys(),1): 
		mg_id = obj._dict['mg_details'][mg]['mg_id']
		ports = obj._dict['mg_details'][mg]['ports']
		ports = [p.split(':')[1] for p in ports]
		mg_vols = obj._dict['mg_details'][mg]['vol_ids']
		_count = 1
		_size = 100
		
		for c in range(int(options.iterations)):
			snapshots, clones = [], [] 

			print "Creating snapshot & clone for existing volumes"
			for ind, _vid in enumerate(mg_vols, 1):
				_sid = obj.create_copy(_vid, 'snapshots', 's_%s_%s'%(ind,c))
				if not _sid :
					return(1)
				snapshots.append(_sid)

				_cid = obj.create_copy(_sid, 'clones', 'c_%s_%s'%(ind,c))
				if not _cid :
					return(1)
				clones.append(_cid)

				if obj.assign_object('volumes', _cid, ports, []) or obj.assign_object('volumes', _sid, ports, []) : 
					return(1)

			out,err = execute_command("nvme list; pnvme --listall")
			print out
			time.sleep(30)

			for _sid, _cid in zip(snapshots, clones):
				if obj.unassign_object('volumes', _cid) or obj.unassign_object('volumes', _sid):
					return(1)

				if obj.del_storage_obj('snapshots', _cid) or obj.del_storage_obj('snapshots', _sid):
					return(1)

			print "\n<><><><><><><><><><Completed %s iterations of parallel ops><><><><><><><><>"%str(c)
			if (c+1) < int(options.iterations):
				print "Sleeping for %s interva"%str(options.interval)
				time.sleep(int(options.interval))
				 
		return(0)



def drives_powercycle(obj, options):
	print "Performing Drive powercycle operations on MG..."
	
	for i, mg in enumerate(obj._dict['mg_details'].keys(),1): 
		mg_id = obj._dict['mg_details'][mg]['mg_id']
		media_slots = obj._dict['mg_details'][mg]['media_slots']
		rebuild_type = obj._dict['mg_details'][mg]['rebuild_type']
		
		print "RebuildType:%s"%str(rebuild_type)
		for c in range(int(options.iterations)):
			#drv = random.choice(media_slots)
			_tmp = c % 3
			drv = (_tmp + 1) if _tmp != 2 else media_slots[-1]

			poweron = 0
			if int(rebuild_type) :
				rs, ds, rp = obj.get_mg_state(mg_id)
				if ds != 'Critical':
					if obj.power_state_change('drives', drv, 'poweroff'):
						return(1)
					obj.get_mg_state(mg_id)
					poweron = 1
				else:
					print "MG in Critical state, no drive shall be poweroff"

			time.sleep(60)

			if poweron :
				rs, ds, rp, rc = obj.get_mg_state(mg_id)
				if (obj.power_state_change('drives', drv, 'poweron')): 
					return(1)

				obj.get_details()		##Need as in rebuild_type 1 drives may change

				if obj.rebuild_mg(mg_id):
					return(1)

			"""
			_it = 0
			while(1):
				rs, ds, rp = obj.get_mg_state(mg_id)
				if int(rp) == 100:
					print "Rebuild Completed..."
					break
				elif _it > 10:
					print "20minutes looped for rebuild to progress\nExiting..."
					break					
				else:
					print "Waiting for rebuild to progress"
					time.sleep(120)
					_it = _it + 1
			"""
		
			print "\n<><><><><><><><><><Completed %s iterations of parallel ops><><><><><><><><>"%str(c)
			if (c+1) < int(options.iterations):
				print "Sleeping for %s interval"%str(options.interval)
				time.sleep(int(options.interval))
				 
	return(0)


def new_objects_create_delete(obj, options):
	print "Performing parallel operations on MG..."
	
	for i, mg in enumerate(obj._dict['mg_details'].keys(),1): 
		mg_id = obj._dict['mg_details'][mg]['mg_id']
		ports = obj._dict['mg_details'][mg]['ports']
		mg_vols = obj._dict['mg_details'][mg]['vol_ids']
		ports = [p.split(':')[1] for p in ports]
		_count = 1
		_size = 100
		
		for c in range(int(options.iterations)):
			print "Creating a new volume, snapshot & clone for the same"
			vol_ids = obj.create_vols(mg_id, _count, _size, '_%s_%s'%(i,c))
			if len(vol_ids) != _count:
				return(1)

			sid = obj.create_copy(vol_ids[0], 'snapshots', 'snap_%s_%s'%(i,c))
			if not sid:
				return(1)

			cid = obj.create_copy(sid, 'clones', 'clone_%s_%s'%(i,c))
			if not cid:
				return(1)

			print "Only Assigning volume & snapshot to ports"
			if obj.assign_object('volumes', vol_ids[0], ports, []) or obj.assign_object('volumes', sid, ports, []) : 
				return(1)

			print "Assigning & Connecting only clones..."
			if obj.assign_object('volumes', cid, ports, []) :
				return(1)
			
			allvols = obj.get_given_parent_obj_info('storage', 'volumes/all')
			for vol in allvols:
				if cid == vol['id']:
					serial = vol['serial']

			obj.get_port_ips(ports)
			print obj._dict['ipdetails']

			print "Connecting clone to host: %s"%serial
			for port in ports:
				out,err = execute_command("nvme connect -t rdma -s 4420 -a %s -n %s"%(obj._dict['ipdetails'][port], serial))
				if err:
					print out, err
					return(1)
			
			out,err = execute_command("nvme list; pnvme --listall")
			print out

			devices, err = execute_command("nvme list | grep %s | grep '^/dev/nvm' | awk '{print $1}'"%serial)

			for dev in devices.splitlines():
				out, err = execute_command("nvme disconnect -d %s"%dev.strip()[5:])
				if err:
					print "ERROR! Failed to disconnect device"
					return(1)

			if obj.unassign_object('volumes', cid) or obj.unassign_object('volumes',vol_ids[0]) or obj.unassign_object('volumes', sid):
				return(1)

			if obj.del_storage_obj('snapshots', cid) or obj.del_storage_obj('snapshots', sid) or obj.del_storage_obj('volumes',vol_ids[0]):
				return(1)

			print "\n<><><><><><><><><><Completed %s iterations of parallel ops><><><><><><><><>"%str(c)
			if (c+1) < int(options.iterations):
				print "Sleeping for %s interva"%str(options.interval)
				time.sleep(int(options.interval))
				 
		return(0)


