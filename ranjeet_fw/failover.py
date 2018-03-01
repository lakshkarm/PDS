import subprocess, time, paramiko, random
from datetime import datetime

fd = None

##Execute command using subprocess
def execute_command(command):
	print command
	fd.write("%s :: %s\n"%(datetime.now().strftime('%B %d %H:%M:%S'),command))
	proc = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	return(proc.communicate())

	
	
##Actual definition that puts down & brings up the single port at a time
def down_up_port(_port):

        print "%s;Putting down port:%s"%(datetime.now().strftime('%B %d %H:%M:%S'),_port)
        cmd = "ifconfig %s down"%_port
        out, err = execute_command(cmd)
        if err:
                print "ERROR! Failed to down the port - %s\n"%_port, err
                return(1)

        time.sleep(10)
        out, err = execute_command("nvme list; pnvme --listall")
        print out

        print "%s;Bringing up port:%s"%(datetime.now().strftime('%B %d %H:%M:%S'),_port)
        cmd = "ifconfig %s up"%_port
        out, err = execute_command(cmd)
        if err:
                print "ERROR! Failed to down the port - %s\n"%_port, err
                return(1)


        return(0)


##Identifies active port
def get_active_port(_ports):
        _active = None

        lines, err = execute_command("pnvme --listall | grep -v -e '----' -e Device -e Path  | grep -A 2 nvme ")
        if err:
		print "ERROR! pnvme command failed:%s"%err
                return _active

	req_line = lines.splitlines()[0] if '(A)' in lines.splitlines()[0] else lines.splitlines()[1]
	if (len(req_line.split())) > 4:
		ip = req_line.split()[-2]
	else:
		ip = req_line.split()[-1]


        subnet = '.'.join(ip.split('.')[:-1])
        for port in _ports.split(","):
                out, err = execute_command("ifconfig %s | grep 'inet'"%port)
                if err:
                        print "ERROR! config details missing for port:%s\n%s"%(port,err)
                        break

                if subnet in out:
                        _active = port

	print "Active port on host:%s"%_active
        return _active


##Flip flap active port, first option of the ports parameter shall be active port
def flip_flap_ports_host(ports, rand):
        active_port = get_active_port(ports)
        if not active_port : 
                print "ERROR! No active port/path detected"
                return(1, None)

	_port = random.choice(ports.split(",")) if rand else active_port
	st = down_up_port(_port)
	##Toggling ports returned non 0
	if st:	
		return(1, None)
	##Toggling ports returned 0 but toggled STANDBY port
	if rand and active_port != _port:
		return(0, None) 

	##Toggling ports succeeded and FO is expected
        return(0, "FO")


def reconnect_devices(rand):
	st, msg = 1, None 
        lines, err = execute_command("pnvme --listall | grep '(A)'")
        if err:
		print "ERROR! pnvme command failed:%s"%err
                return _active

	if len(lines.splitlines()[0].split()) > 4:
		active_devs, err = execute_command("pnvme --listall | grep '(A)' | awk '{print $2\":\"$4\":\"$5}'")
		active_devs = active_devs.splitlines()

		standby_devs = []
		temp_devs, err = execute_command("pnvme --listall | grep nvme.* -w | grep -v '(A)' | awk '{print $1}'")
		temp_devs = temp_devs.splitlines()
		for _dev in temp_devs:
			out, err = execute_command("pnvme --list %s | grep nvme.* | awk '{print $2\":\"$4\":\"$5}'"%_dev)
			standby_devs.append(out.strip())

	elif len(lines.splitlines()[0].split()) < 4:
		temp_devs, err = execute_command("pnvme --listall | grep '(A)' | awk '{print $1}'")
		temp_devs = temp_devs.splitlines()
		active_devs = []
		for _dev in temp_devs:
			out, err = execute_command("pnvme --list %s | grep nvme.* | awk '{print $2\":\"$4\":\"$5}'"%_dev)
			active_devs.append(out.strip())

		standby_devs, err = execute_command("pnvme --listall | grep nvme.* -w | grep -v '(A)' | awk '{print $2\":\"$4\":\"$5'}")
		standby_devs = standby_devs.splitlines()

	print "Active devices on host:",active_devs
	print "Standby devices on host:", standby_devs

	devs = random.choice([standby_devs, active_devs]) if rand else active_devs
	print datetime.now().strftime('%B %d %H:%M:%S')
	print "Choosen devices to ReConnect:", devs
	for dev in devs:
		out, err = execute_command("nvme disconnect -d %s"%dev.split(':')[0])
		if err:
			print "ERROR! Failed to disconnect\n%s"%err
			return(1, None)

	time.sleep(10)
        out, err = execute_command("nvme list; pnvme --listall")
        print out
	for dev in devs:
		out, err = execute_command("nvme connect -t rdma -s 4420 -n %s -a %s"%(dev.split(':')[1], dev.split(':')[2]))
		if err:
			print "ERROR! Failed to connect\n%s"%err
			return(1, None)
		time.sleep(3)

	st, msg = 0, None
	if devs == active_devs:
		st, msg = 0, "FO"

	return(st, msg)


def host_side_ops(ports, rand):
	st, msg = 1, None 
	ch = random.choice(['ports', 'disconnect'])
	print "Performing %s choice on host"%(ch)
	if ch == 'ports':
		st, msg = flip_flap_ports_host(ports, rand)
	else:
		st, msg = reconnect_devices(rand)

	return(st, msg)



##################################################################################################################################

def execute_ssh_cmd(cmd, ssh):
	print "%s;%s"%(datetime.now().strftime('%B %d %H:%M:%S'),cmd)
	fd.write("%s :: %s\n"%(datetime.now().strftime('%B %d %H:%M:%S'), cmd))
	sin, sout, serr = ssh.exec_command(cmd)
	out, err = sout.readlines(), serr.readlines()
	print out, err
	return(out, err)
	

def get_active_node(_nodes, ssh):
	_active = None
	_node = _nodes.split(',')[0]
	cmd = "ssh %s 'grep -m 1 State /proc/dms/iocvolume'"%_node.split(':')[0]
	out, err = execute_ssh_cmd(cmd, ssh)
	st = out[0].strip().split()[-1]
	
	_active = _node.split(':')[0] if st == "READY" else _nodes.split(',')[1].split(':')[0]

	print "Active node on chassis:%s"%_active
	return(_active)


def flip_flap_port_node(_node, nodes_with_ports, ssh):
	_temp = {}
	for n_w_p in nodes_with_ports.split(','):
		_temp[n_w_p.split(':')[0]] = n_w_p.split(':')[1]

        print "%s;Putting down port on %s:%s"%(datetime.now().strftime('%B %d %H:%M:%S'),_node,_temp[_node])
	cmd = "ssh %s 'ifconfig %s down'"%(_node, _temp[_node])
	out, err = execute_ssh_cmd(cmd, ssh)

        time.sleep(10)
        out, err = execute_command("nvme list; pnvme --listall")
        print out

        print "%s;Bringing up port on %s:%s"%(datetime.now().strftime('%B %d %H:%M:%S'),_node,_temp[_node])
	cmd = "ssh %s 'ifconfig %s up'"%(_node, _temp[_node])
	out, err = execute_ssh_cmd(cmd, ssh)
	return(out, err)



def power_cycle_node(node, obj):
	if obj.power_state_change('controllers', node, 'poweroff') or obj.power_state_change('controllers', node, 'poweron'):
		return(1)

	return(0)


def node_side_ops(obj, rand):
	nodes_with_ports = obj._dict['node_ports']
	try:
		ssh = paramiko.SSHClient()
		ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
		ssh.connect(obj._dict['ip'], 22, obj._dict['username'], obj._dict['password'])
	except:
		print "ERROR! Unable to get connection"
		return(1)

	active_node = get_active_node(nodes_with_ports, ssh)
	_node = random.choice(nodes_with_ports.split(",")) if rand else active_node
	_node = _node.split(':')[0]
	
	out, err, cmd = None, None, None
	ch = random.choice(['port', 'offon', 'crash', 'reset'])
	print "Performing %s choice on %s"%(ch, _node)
	if ch == 'port':
		out, err = flip_flap_port_node(_node, nodes_with_ports, ssh)
	elif ch == 'crash':
		cmd = "ssh %s 'echo c > /proc/sysrq-trigger &'"%_node
	elif ch == 'reset':
		cmd = "ssh %s 'echo b > /proc/sysrq-trigger &'"%_node
	elif ch == 'offon':
		execute_ssh_cmd("echo 'PowerCycling this Controller' > /dev/kmsg", ssh)
		err = obj.power_state_change('controllers', _node[4:], 'poweroff') | obj.power_state_change('controllers', _node[4:], 'poweron')
	
	if cmd:
		out, err = execute_ssh_cmd(cmd, ssh)	
		print "Waiting for node to boot up!"
		if obj.check_obj_status('controllers', _node[4:], "Active") :
			return(1, None)

	ssh.close()
	if err:
		return(1, None)

	if rand and active_node != _node:
		return(0, None)

	return(0, "FO")


def check_active_path_availability():
	mpdevs, err = execute_command("lsblk | grep ^mpnvm  -c")
	if err or not int(mpdevs):
		print "ERROR! not able to read MP devices"
		return(1)

	singledevs, err = execute_command("lsblk | grep ^nvm  -c")
	if err or not int(singledevs):
		print "ERROR! not able to read MP devices"
		return(1)

	if int(singledevs) != 2 * int(mpdevs):
		print "ERROR! Seems all paths are connected totally"
		return(1)

	out, err = execute_command("pnvme --listall | grep -c '(A)'") 
	if int(out) != int(mpdevs):
		print "ERROR! Not all multipath devices active path detected"
		return(1)

	out, err = execute_command("pnvme --listall | grep -w P") 
	if out:
		print "ERROR! Passive paths detected"
		return(1)

	return(0)



def trigger_fo(options, api_obj):
	global fd
	if 'host_ports' in api_obj._dict.keys() and len(api_obj._dict['host_ports'].split(",")) != 2:
		print "ERROR! Requires exactly 2 ports!"
		return(1)

	if 'node_ports' in api_obj._dict.keys() and len(api_obj._dict['node_ports'].split(",")) != 2:
		print "ERROR! Requires exactly 2 nodes!"
		return(1)

	logger = "/home/testing/FailOver_%s.log"%datetime.now().strftime('%H_%M_%S')
	print "FO sequence logger: %s"%logger
	fd = open(logger, 'w')
	out, err = execute_command("mkdir -p /home/testing/")
	fd.write("%s :: Starting FO sequence\n"%datetime.now().strftime('%B %d %H:%M:%S'))

        out, err = execute_command("nvme list; pnvme --listall")
	print out
	i, flag = 1, 0
	while(i <= int(options.iterations)):
		if (check_active_path_availability()):
			flag = 1
			break 

        	execute_command("dmesg -c > /dev/null")

		if 'host_ports' in api_obj._dict.keys() and 'node_ports' in api_obj._dict.keys():
			st, msg = node_side_ops(api_obj, options.rand) if i%2 else host_side_ops(api_obj._dict['host_ports'], options.rand) 
		elif 'host_ports' in api_obj._dict.keys():
			st, msg = host_side_ops(api_obj._dict['host_ports'], options.rand) 
		elif 'node_ports' in api_obj._dict.keys():
			st, msg = node_side_ops(api_obj, options.rand)

		if st:
			print "ERROR! Unexpected error!"
			flag = 1
			break 

		time.sleep(45)		#Inconsistency in calculated time to reconnect
		print "Definitions returned %s !\nValidating...."%msg

        	out, err = execute_command("nvme list; pnvme --listall")
		print out

		fo, err = execute_command("dmesg -T | grep 'nvme_trigger_failover'")
		print fo, err

		if msg == "FO" and fo:
			print "FailOver Triggered as expected"
			out, err = execute_command("dmesg -T | grep -e 'Add nvme.* to mpath group' -e 'nvme.*: Successfully reconnected'")
			print out
			if len(out.splitlines()) != len(fo.splitlines()):
				print "ERROR! Mismatch in FO requests & reconnected objects"
				flag = 1
				break 

		elif msg == "FO" and (not fo):
			print "ERROR! Expecting failover but not noticed nvme_trigger_failover"
			flag = 1
			break 

		elif msg != "FO" and fo:
			print "ERROR! Not expecting failover but noticed nvme_trigger_failover"
			flag = 1
			break 

                print ">>>>>>>>>>>>>>>>>>>>Completed %s iterations of FO<<<<<<<<<<<<<<<<<<<<<<<\n"%str(i)

		i = i + 1
		if i > int(options.iterations) :
			break
		print "Waiting for given interval:%s"%(str(options.interval))
	        time.sleep(int(options.interval))

	if flag:
		return(1)
	fd.write("%s :: Completed FO sequence\n"%datetime.now().strftime('%B %d %H:%M:%S'))
	fd.close()
	print "FO sequence logger: %s"%logger
	return(0)


