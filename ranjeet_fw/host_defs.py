import subprocess, time, sys, random, datetime, os

def execute_command(command):
	print command
	proc = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	return(proc.communicate())

##Connect-all per port
def connect_volumes(node_ips):
	print "\nConnecting volumes based on node IP list:"
	for ip in node_ips:
		time.sleep(5)
		out, err = execute_command("nvme connect-all -s 4420 -t rdma -a %s"%ip)
		if err:
			print "ERROR! Failed to connect-all:%s"%err
			return(1)
	out, err = execute_command("nvme list; pnvme --listall")
	print out
	return(0)


##Return cumulative size from list of devices
def get_total_sz_available(devices):
	print "\nCalculating available size from all devices"
	tot_sz = 0
	for dev in devices:
		out, err = execute_command("blockdev --getsize64 %s"%dev) 
		if not err:
			tot_sz = tot_sz + int(out)

	sz_in_gigs = tot_sz/1024/1024/1024
	##Reducing 10GB for safe side
	tot_sz = tot_sz - int(10*1024*1024*1024)
	print "Total Size available: %s"%str(tot_sz)
	return int(tot_sz)


##Identifies connected volumes either to mpnvme* or nvme*
def check_available_devices():
	print "\nChecking for LVM's..."
	out, err = execute_command("ls /dev/mapper/pd_vol*")
	lvms, multipath = 0, 0
	if not err:
		lvms = 1
		avail_devs = out.splitlines()
	
	if not lvms:
		print "Checking for Multipath devices.."
		out, err = execute_command("ls /dev/mp*")
		if not err:			##Multipath devices detected
			multipath = 1

	if not multipath and not lvms:
		print "Checking for Single path devices.."
		out, err = execute_command("ls /dev/nvme*n*")
		if err:
			print "\nERROR! Neither Single nor Multi path devices detected"
			return([])

	return out.splitlines()




##Formats & mounts devices, LV's if detected next check to mpnv* then to nvme*
def create_mount_fs(fs_type):
	print "\nFormatting devices to mount"
	avail_devs = check_available_devices()
	if not avail_devs:
		return(1)

	if fs_type == "xfs":
		fs_type = fs_type + " -f"

	for i, dev in enumerate(avail_devs, 1):
		cmd = "mkfs -t %s %s "%(fs_type,dev)
		out, err = execute_command(cmd)
		if fs_type[:-1] == "ext" and "Writing superblocks and filesystem accounting informatio" not in out:
			print "ERROR! Failed to format:%s\n"%cmd, err
			return(1)
		if fs_type == "xfs" and err:
			print "ERROR! Failed to format:%s\n"%cmd, err
			return(1)
	
		execute_command("mkdir -p /mnt_test%s"%i)
		cmd = "mount %s /mnt_test%s"%(dev, i)
		out, err = execute_command(cmd)
		if err:
			print "ERROR! Failed to format:%s\n"%cmd, err
			return(1)
	
	out, err = execute_command("nvme list; df -h | grep mnt_test; echo ; lsblk | grep -e pd_vol -e nvm*; echo; mount | grep mnt_test")
	print out
	return(0)


##Unmount objects
def umount_objs():
	print "\nUNMOUNTING..."
	avail_devs = check_available_devices()

	_tdevs, err = execute_command("df | grep /mnt_test | awk '{print $1}'")
	if not _tdevs:
		return(0)

	for dev in _tdevs.splitlines():
		cmd = "umount %s"%dev
		out, err = execute_command(cmd)
		if out or err:
			print "ERROR! Failed to unmount:%s\n"%dev, err, out
			return(1)

	out, err = execute_command("nvme list; df -h | grep mnt_test; echo ; lsblk | grep -e pd_vol -e nvm*; echo; mount | grep mnt_test")
	print out
	return(0)

##Disconnect objects
def disconnect_objs():
	print "\nDisconnecting objects..."
	out, err = execute_command("nvme list")
	print out

	out, err = execute_command("ls /dev/nvme*n* | sort")
	if err:
		print "WARNING?! No objects detected\n%s"%err
		return(0)

	print out
	for dev in out.splitlines():
		out, err = execute_command("nvme disconnect -d %s"%(dev[5:]))
		if err:
			print "ERROR! unable to disconnect %s\n%s"%(dev,err)
			return(1)

	out, err = execute_command("nvme list")
	print out
	time.sleep(7)
	return(0)


##Create Linux LVM of equal sizes
def linux_lvm(_cnt):
	print "\nTarget to create %s LV's"%_cnt
	avail_devs = check_available_devices()		
	avail_sz = get_total_sz_available(avail_devs)

	sz = int(avail_sz) / int(_cnt)
	sz = sz / 1024 / 1024 / 1024
	print "Creating %s volumes each of size(G): %s"%(str(_cnt), str(sz))

	cmd = "pvcreate %s"%(' '.join(avail_devs))
	out, err = execute_command(cmd)
	if err:
		print "ERROR! Not able pvcreate devices:%s\n"%cmd, err
		return (1)

	cmd = "vgcreate pd_vol %s"%(' '.join(avail_devs))
	out, err = execute_command(cmd)
	#if "successfully" not in err:			##In a multipath scenario dupliate PV's will be seen
	if not out:
		print "ERROR! Not able vgcreate pd_vol:%s\n"%cmd, err
		return (1)

	for i in range(1,int(_cnt)+1):
		cmd = "lvcreate -L%sg -nlv%s pd_vol"%(str(sz),str(i))
		out, err = execute_command(cmd)
		#if "successfully" not in err:			##In a multipath scenario dupliate PV's will be seen
		if not out:
			print "ERROR! Not able lvcreate :%s\n"%cmd, err
			return (1)

	out, err = execute_command("pvs;echo;vgs;echo;lvs;echo")
	print out
	return(0)


##Deletes LVM
def cleanup_lvm(_cnt):
	out, err = execute_command("ls /dev/mapper/pd_vol* ")
	if not out:
		return(0)

	lvms_devs = out.splitlines()
	
	print "Removing LV's ifany..."
	for i in range(0, len(lvm_devs)):
		cmd = "lvremove -f /dev/pd_vol/lv%s"%str(i+1)
		out, err = execute_command(cmd)
		if not out:
			print "ERROR! Not able lvremove :%s\n"%cmd, err
			return(1)

	cmd = "vgremove pd_vol "
	out, err = execute_command(cmd)
	#if "successfully" not in err:			##In a multipath scenario dupliate PV's will be seen
	if not out:
		print "ERROR! Not able vgremove pd_vol:%s\n"%cmd, err
		return (1)

	avail_devs = check_available_devices()		
	cmd = "pvremove %s"%(' '.join(avail_devs))
	out, err = execute_command(cmd)
	if not out:
		print "ERROR! Not able pvremove devices:%s\n"%cmd, err
		return (1)

	

def cleanup(count, fs_type):
	print "\nCLEANUP:\n"
	if umount_objs():
		return(1)
	
	if cleanup_lvm(count):
		return(1)

	if disconnect_objs():
		return(1)



def get_valid_pattern(target, bits=16):
	filepath = "/home/testing/pattern_file_%s"%target
	bits = int(bits)
	pattern = "0x" + ''.join(random.choice('0123456789abcdef') for i in range(bits))

	if os.path.isfile(filepath):
		os.unlink(filepath)

	with open(filepath, 'wb') as fd:
		fd.write('pattern:' + pattern)

	if not os.path.isfile(filepath):
		print "ERROR! Failed to write pattern to file %s"%filepath

	return pattern



## FIO configuration file
def fio_jobfile(fs_type):

	avail_devs = check_available_devices()
	if not avail_devs:
		return None, None

	out, err = execute_command("mkdir -p /home/testing/")
	suffix = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
	jobfile = "/home/testing/fiojob_%s"%suffix
	logfile = "/home/testing/fiolog_%s"%suffix
	default = "[global]\ndirect=1\nioengine=libaio\nnumjobs=1\ngroup_reporting\nrefill_buffers\nrandrepeat=0\nthread\nsize=100%\n"
	default = default + "verify=crc64\nverify_fatal=1\nverify_interval=1024\nverify_dump=1\nerror_dump=1\n\n\n"

	fd = open(jobfile, 'w')
	fd.write(default)

	rd = open("tem_rdjob", 'w')
	
	_grp = "stonewall=1\n"
	for dev in avail_devs:
		head = dev[5:].replace('/','_')
		pattern = get_valid_pattern(head) 
		depth = random.choice(["16", "4", "128", "32", "256", "64", "8", "512"])
		bs = random.choice(["1M", "512K", "2M", "4M", "16K", "32K", "128K", "64K", "3M"])
		wroptions = "[%s]\nrw=write\ndo_verify=0\nverify_pattern=%s\niodepth=%s\nbs=%s\n"%(head,pattern,str(depth),str(bs))
		rdoptions = "[%s]\n%srw=read\ndo_verify=1\nverify_pattern=%s\niodepth=%s\nbs=%s\n"%(head,_grp,pattern,str(depth),str(bs))
		addtlopts = "filename=%s\n\n"%dev
		_grp = ""

		out, err = execute_command("mount | grep %s"%dev)
		if out: 
			cmd = "df | grep %s -w | awk '{print $(NF-2),$(NF)}'"%dev
			out, err = execute_command(cmd)
			if err:
				print "ERROR! unable to get mount point and size:%s\n%s\n%s"%(cmd,err,out)
				return(1)
			_sz = (int(out.split(' ')[0])) * 1024			##Bytes
			_sz = _sz * 85 / 100		## 75% of free space
			nfiles= random.choice([16, 4, 64, 1, 8, 32])
			sz_f = int(_sz) / nfiles
			sz_f = sz_f / 1024 / 1024 / 1024
			sz_gs = str(sz_f) + "G"
			addtlopts = "directory=%s/\nnrfiles=%s\nfilesize=%s\n\n"%(out.split(' ')[1].strip(),str(nfiles),sz_gs)

		fd.write(wroptions + addtlopts)
		rd.write(rdoptions + addtlopts)

	rd.close()

	with open("tem_rdjob", 'r+') as rd:
                lines = rd.readlines()

        fd.write("\n\n%s"%''.join(lines))

	fd.close()
	return(jobfile, logfile)


##Run io job
def run_io_job(jobfile, logfile):
	if 'fio' in jobfile:
		cmd = "nohup time fio %s &> %s"%(jobfile, logfile)
	else:
		cmd = "nohup time /root/vdbench/vdbench -v -f %s &> %s"%(jobfile, logfile)

	out, err = execute_command(cmd)
	print out, err
	

def verify_io_log(logfile):
	fail_words = ["error", "verify", "Invalid", "wanted", "bad magic header"]
	flag = 0
	
	with open(logfile, 'r+') as fd:
		lines = fd.readlines()

	for word in fail_words:
		if word in lines: 
			print "ERROR! Found %s in io log"%(word)
			flag = 1
	return(flag)


def vdbench_jobfile(fs_type):

	avail_devs = check_available_devices()
	if not avail_devs:
		return None, None

	out, err = execute_command("mkdir -p /home/testing/")
	suffix = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
	jobfile = "/home/testing/vdbenchjob_%s"%suffix
	logfile = "/home/testing/vdbenchlog_%s"%suffix

	fd = open(jobfile, 'w')
	sd, wd, rd =  "", "", ""
	for i, dev in enumerate(avail_devs, 1):
		bs = random.choice(["1M", "512K", "2M", "4M", "16K", "32K", "128K", "64K", "3M"])
		threads = random.choice(["16", "4", "128", "32", "256", "64", "8"])

		out, err = execute_command("mount | grep %s"%dev)
		if out: 
			cmd = "df | grep %s | awk '{print $(NF-2),$(NF)}'"%dev
			out, err = execute_command(cmd)
			if err:
				print "ERROR! unable to get mount point and size:%s\n%s\n%s"%(cmd,err,out)
				return(1)
			_sz = (int(out.split(' ')[0])) * 1024			##Bytes
			#_sz = _sz - (15 * 1024 * 1024 * 1024)
			#_sz = _sz * 2 / 3
			_sz = _sz * 85 / 100		## 75% of free space
			nfiles= random.choice([16, 4, 64, 1, 8, 32])
			sz_f = int(_sz) / nfiles
			sz_f = sz_f / 1024 / 1024 / 1024
			sz_gs = str(sz_f) + "G"
			sd = "%s\nfsd=fsd%s,anchor=%s,depth=1,width=1,files=%s,size=%s"%(sd, str(i),out.split(' ')[1].strip(), str(nfiles), sz_gs)
			wd = "%s\nfwd=fwd%s,fsd=fsd%s,rdpct=0,xfersize=%s,fileselect=random,fileio=random,threads=%s"%(wd, str(i), str(i), bs, threads)
			rd = "%s\nfwd=fwd%s,fsd=fsd%s,rdpct=100,xfersize=%s,fileselect=random,fileio=random,threads=%s"%(rd, str(len(avail_devs)+i), str(i), bs, threads)

		else:
			sd = "%s\nsd=sd%s,lun=%s,openflags=o_direct,threads=%s"%(sd, str(i),dev, threads)
			wd = "%s\nwd=wd%s,sd=sd%s,rdpct=0,xfersize=%s"%(wd, str(i), str(i), bs)
			rd = "%s\nwd=wd%s,sd=sd%s,rdpct=100,xfersize=%s"%(rd, str(len(avail_devs)+i), str(i), bs)

	fd.write("%s\n%s\n%s\n"%(sd, wd,rd))
	rd = "\nrd=rd1,wd=(wd1-wd%s),iorate=max,elapsed=2h,interval=30"%(str(len(avail_devs)))
	rd = "%s\nrd=rd2,wd=(wd%s-wd%s),iorate=max,elapsed=2h,interval=30"%(rd, str(len(avail_devs)+1), str(2*len(avail_devs)))
	
	out, err = execute_command("mount | grep %s"%dev)
	if out: 
		rd = "\nrd=rd1,fwd=(fwd1-fwd%s),fwdrate=max,format=yes,elapsed=1h,interval=30"%(str(len(avail_devs)))
		rd = "%s\nrd=rd2,fwd=(fwd%s-fwd%s),fwdrate=max,format=yes,elapsed=1h,interval=30"%(rd,str(len(avail_devs)+1), str(2*len(avail_devs)))


	fd.write(rd+"\n")
	fd.close()

	return(jobfile, logfile)


def get_io_jobfile(fs_type):
	ch = random.choice(['fio', 'vdbench'])
	ch = 'fio'
	if ch == 'fio':
		return(fio_jobfile(fs_type))
	else:
		return(vdbench_jobfile(fs_type))
	


def perform_ios(op, dets):
	_d = {'pattern':None, 'depth':None, 'bs':None, 'nrfiles':None, 'filesize':None} 
	
	avail_devs = check_available_devices()
	if not avail_devs:
		return (_d)

	for dev in avail_devs:
		head = dev[5:].replace('/','_')

	cmd = "fio --name=job --direct=1 --ioengine=libaio --numjobs=1 --group_reporting --size=100% " 

	if op == 'write':
		pattern = get_valid_pattern(head) 
		depth = random.choice(["16", "4", "128", "32", "256", "64", "8", "512"])
		bs = random.choice(["1M", "512K", "2M", "4M", "16K", "32K", "128K", "64K", "3M"])
		cmd = cmd + " --bs=%s --iodepth=%s --verify_pattern=%s --do_verify=0 "%(bs, depth, pattern)
		_d = {'pattern': pattern, 'depth': depth, 'bs': bs} 
	else:
		cmd = cmd + " --bs=%s --iodepth=%s --verify_pattern=%s "%(dets['bs'], dets['depth'], dets['pattern'])
		cmd = cmd + " --verify_fatal=1 --verify_interval=1024 --verify_dump=1 --error_dump=1 --do_verify=1 " 
		_d = {'pattern': dets['pattern'], 'depth': dets['depth'], 'bs': dets['bs']} 

	addtlopts = "--filename=%s"%dev

	out, err = execute_command("mount | grep %s"%dev)
	if out: 
		_cmd = "df | grep %s | awk '{print $(NF-2),$(NF)}'"%dev
		out, err = execute_command(_cmd)
		if err:
			print "ERROR! unable to get mount point and size:%s\n%s\n%s"%(_cmd,err,out)
			return ({'pattern':None, 'depth':None, 'bs':None, 'nrfiles':None, 'filesize':None} )

		if op == 'write':
			_sz = (int(out.split(' ')[0])) * 1024			##Bytes
			_sz = _sz * 85 / 100		## 75% of free space
			nfiles= random.choice([16, 4, 64, 1, 8, 32])
			sz_f = int(_sz) / nfiles
			sz_f = sz_f / 1024 / 1024 / 1024
			sz_gs = str(sz_f) + "G"
			addtlopts = " --directory=%s --nrfiles=%s --filesize=%s "%(out.split(' ')[1].strip(),str(nfiles),sz_gs)
			_d['nrfiles'] = nfiles
			_d['filesize'] = sz_gs
		else:
			addtlopts = " --directory=%s --nrfiles=%s --filesize=%s "%(out.split(' ')[1].strip(),dets['nrfiles'],dets['filesize'])
			_d['nrfiles'] = dets['nrfiles']
			_d['filesize'] = dets['filesize']


	cmd = cmd + " --rw=%s "%op + addtlopts
	out, err = execute_command('%s '%cmd) 
	print "OUT:" + out
	print "ERR:" + err
	if err:
		return ({'pattern':None, 'depth':None, 'bs':None, 'nrfiles':None, 'filesize':None} )

	return (_d)

