import requests, json, time, random
from requests.packages.urllib3.exceptions import InsecureRequestWarning
#requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
requests.packages.urllib3.disable_warnings()
#***************************************************************************************************************************************************

class TARGET_API():

	def __init__(self, config_file):
		with open(config_file, 'r') as fd:
			self._dict = json.load(fd)

		self.c_type = "application/json;charset=UTF-8"
		#self.avail_mg_types = ["RAID-6 (6+2+1)", "RAID-6 (15+2+1)", "RAID-6 (7+2)", "RAID-0 (9+0)", "RAID-0 (18+0)", "RAID-6 (16+2)"]
		self.avail_mg_types = ["RAID-6 (6+2+1)", "RAID-6 (7+2)"] 
		self._dict['ipdetails'] = {}
		self.mg_key = 'test_mg'
		print self._dict

	def get_session(self):
        	s = requests.session()
	        r = s.post("https://"+self._dict['ip']+"/api/v1.0/auth/login?password="+self._dict['password']+"&username="+self._dict['username'], {"Accept": "application/json"}, verify=False)
        	self.session_id = r.cookies["JSESSIONID"]
	        self.session_token = r.cookies["XSRF-TOKEN"]
		#print self.session_id +"\n"+self.session_token	
		if not (self.session_id or self.session_token):
			print "ERROR! Unable to get session"
			return(1)
	

	def run_api(self, _api, _data, _method="GET", c_type=None):
		
		if self.get_session():
			return(1)

		c_type = self.c_type if not c_type else c_type
		header = {"Content-Type": c_type, "XSRF-TOKEN": str(self.session_token),"X-XSRF-TOKEN":str(self.session_token),"Referer":"https://"+self._dict['ip']+"/swagger-ui.html" }
		cookie = {"JSESSIONID": str(self.session_id)}
		_data = json.dumps(_data)

		print _api, _data
		#print c_type, header, cookie

		if _method == "POST":
			response = requests.request(_method, _api, headers=header, data=_data, cookies=cookie, verify=False)
		else:		##GET
			response = requests.request(_method, _api, headers=header, cookies=cookie, verify=False)

		text = json.loads(response.text)
		st =  int(response.status_code)
		#print "==========\n%s::%s\n========"%(str(st), str(text))
		if _method == "POST":
			if (st != 200) or (int(text['error']) != 0):
				print "ERROR! API request returned failure::\nSTATUS = %s\nTEXT = %s"%(st, text)
				return (-1, text)

			#if 'taskid_list' in text.keys() and self.check_task_status(text['taskid_list']):
			if 'taskid_list' in text.keys():
				_ids = text['taskid_list']
				for _id in _ids:
					if self.check_task_status(_id):
						return(-1, text)
			elif 'taskid' in text.keys() and self.check_task_status(text['taskid']):
				return(-1, text)

		elif (_method == "GET") and (st != 200):
			print "ERROR! API request returned failure::\nSTATUS = %s\nTEXT = %s"%(st, text)
			return (-1, text)

		return (st, text) 


	"""
	GETS: 	MediaGroups, MediaGroupDefinitions, zoneinfo, volumes, clones, copies, drives, medias
		Volumes by consumers/initiators, by networks need to construct by callers
		EX: storage/volumes/*vol_id*/consumers, storage/volumes/*vol_id*/networks, storage/volumes/all
	 	notification/tasks
		notification/tasks/*task_id*
		notification/alarmthresholds
		notification/alarmlogs?timestamp=*utc_time_stamp*
		chassis/object_id?object_type=*object_type*&object_name=*object_name*
		chassis/controllers?type=*ctlr_type*
		chassis/controllers/*controller_no*/networks
		chassis/controllers?type=1
		chassis/baseinfo
		chassis/inventory
		chassis/capacity
	"""
	def get_given_parent_obj_info(self, parent, obj):
		api = "https://"+self._dict['ip']+"/api/v1.0/%s/%s"%(parent, obj)

		st, op = self.run_api(api, None)
		if st == -1:
			print "ERROR! Failed to get all details"
			return None
	
		return op
	

	def check_task_status(self, tid):
		if type(tid) is list:
			for _id in tid[::-1]:
				return(self.check_task_status(_id))
		retry = 0
		while(1):
			summary = self.get_given_parent_obj_info("notification", "tasks/%s"%tid)
			if 'Completed' in summary['displayState'] or int(summary['state']) == 0:
				return(0)
			if retry < 12:
				time.sleep(7)
				retry = retry + 1
				#print "\nRETRYING"
			else:
				print "ERROR! Exhausted retry counts to check task status, failing"
				break

		return(1)
		
			
	def create_media_group(self, name, zone, raid_type):
		print "\nCreating MediaGroup:"
		data = {}
		data['name'] = name 
		data['media_zone'] = zone 
		data['media_group_type'] = raid_type 
		api = "https://"+self._dict['ip']+"/api/v1.0/storage/mediagroups/create"

		st, text = self.run_api(api, data, "POST")
		if st == -1:
			print "ERROR! Failed to create mediagroup(s)"
			return None

		print "MediaGroup ID:%s"%(text['groupid'])
		return(text['groupid'])


	def create_volume(self, mg_id, sz, name, reserv):
		data = {
			"strpsize": 4,
			"flavor" : "INSANE",
			"rw": 85,
		        "wl": "Analytics",
			"flavor" : "INSANE"
			}
		data["media_group_id"] =  mg_id
		data['size'] =  int(sz)
		data['name'] = name
		data['reservation'] = reserv

		api = "https://"+self._dict['ip']+"/api/v1.0/storage/volumes/create"
		st, text = self.run_api(api, data, "POST")
		if st == -1:
			print "ERROR! Failed to create volume(s)"
			return None
	
		print "VolumeID: %s"%text['volumeid']
		return text['volumeid']


	def create_copy(self, pid, copy_type, prefix):
		if copy_type not in ('snapshots', 'clones'):
			print "ERROR! Unknow copy type"
			return(1)
		print "\nCreating %s"%copy_type
		cid = None
		data = {}
		data["name"] = "%s_%s"%(copy_type[:4],prefix)
		data["parent_id"] = pid
		#data["reservation"] = 0 if copy_type == 'snapshots' else random.choice([10, 30, 50, 20, 80, 60, 100, 90, 70, 40])
		data["reservation"] = 0 if copy_type == 'snapshots' else 100 
		data["type"] = "Snapshot" if copy_type == 'snapshots' else 'Clone'

		api = "https://"+self._dict['ip']+"/api/v1.0/storage/snapshots/create"
		st, text = self.run_api(api, data, "POST")
		if st == -1:
			print "ERROR! Failed to create copy!"
			return(cid)
	
		cid = text['snapshotid']
		print "CopyID: %s"%cid
		return (cid)


	def del_storage_obj(self, objtype, objid): 
		if objtype not in ('volumes', 'snapshots', 'clones'):
			print "ERROR! Not an valid object"
			return(1)

		print "\nDeleting %s"%objtype
		data = {}

		api = "https://"+self._dict['ip']+"/api/v1.0/storage/%s/%s/delete"%(objtype, objid)
		st, text = self.run_api(api, data, "POST")
		if st == -1:
			print "ERROR! Failed to delete object(s)"
			return(1)
		
		return(0)


	def del_media_group(self, ids=[]):
		print "\nDeleting MediaGroup"
		data = {} 
		mgs = self._dict['mg_details'].keys() if not ids else ids

		for mg in mgs:
			api = "https://"+self._dict['ip']+"/api/v1.0/storage/mediagroups/%s/delete"%self._dict['mg_details'][mg]['mg_id']

			st, text = self.run_api(api, data, "POST")
			if st == -1:
				print "ERROR! Failed to delete object(s)"
				return(1)

		return(0)


	def assign_object(self, objtype, objid, ports, hostnqn=[]):
		print "\nAssigning Object"
		data = {}
		data['ports'] = ports
		if objtype == 'volumes':
			data['hostnqn'] = hostnqn

		api = "https://"+self._dict['ip']+"/api/v1.0/storage/%s/%s/assign"%(objtype, objid)
		st, text = self.run_api(api, data, "POST")
		if st == -1:
			print "ERROR! Failed to Assign object to ports"
			return(1)

		return(0)
		

	def unassign_object(self, objtype, objid):
		print "\nUnassigning object"
		data = {}

		api = "https://"+self._dict['ip']+"/api/v1.0/storage/%s/%s/unassign"%(objtype, objid)
		st, text = self.run_api(api, data, "POST")
		if st == -1:
			print "ERROR! Failed to unassign object" 
			return(1)

		return(0)


	def get_port_ips(self, ports):
		print "\nGetting IP details for ports:",ports
		for port in ports:
			if port in self._dict['ipdetails'].keys():
				continue

			#node = port.split('-')[1].split('/')[0]			##40g-4/1
			node = port.split(':')[0]

			summary = self.get_given_parent_obj_info("chassis", "controllers/%s/networks"%node)
			for ioc in summary:
				if ioc['slot'] == port.split(':')[1]:
					self._dict['ipdetails'][port] = ioc['ipaddr']

		return(0)


	def check_obj_status(self, model, dev, exp_str):
		#_buf = 120 if model not in('controllers') else 60
		_buf = 90
		time.sleep(_buf)	##Node takes 3min to boot up
			
		_max = 25 if exp_str == "Active" else 10
		retry,  _state = 0, None
		while(1):	
			if model == 'controllers':
				controllers = self.get_given_parent_obj_info("chassis", "%s?type=1"%model)
				for ioc in controllers:
					if ioc['slot'] == str(dev) and ioc['displayState'] in exp_str :
						return(0)
					_state = ioc['displayState']
			elif model == 'drives':
				drives = self.get_given_parent_obj_info("chassis", "%s"%model)
				for drv in drives:
					if drv['id'] == str(dev) and drv['displayPresenceState'] in exp_str:
						return(0)
					_state = drv['displayPresenceState']

			if retry > _max:
				print "ERROR! Exhausted retries to check controller status, Failing"
				return(1)
	
			time.sleep(7)
			retry = retry + 1

		print "State of %s is expected %s but API returned %s"%(model, exp_str, )
		return (1)
				

	def power_state_change(self, model, dev, state=None):
		if model not in('controllers', 'drives'):
			print "ERROR! Model not read properply"
			return(1)

		if not state:
			print "ERROR! Power state not defined"
			return(1)

		print "\nChanging Power state for %s:%s to %s"%(model,dev, state)
		
		data = {"device_list":[int(dev)]}
		api = "https://172.25.26.43/api/v1.0/chassis/%s/%s"%(model,state)
		st, text = self.run_api(api, data, "POST")
		if st == -1:
			print "ERROR! Failed to %s controller %s"%(state, str(dev))
			return(1)

		if state == "poweron":
			return(self.check_obj_status(model, dev, ("Active")))
		else:
			return(self.check_obj_status(model, dev, ('Powered Off', 'Powered-Off')))


	def get_mg_state(self, mg_id):
		summary = self.get_given_parent_obj_info('storage', 'mediagroups')
		if not summary:
			return(1)

		rs, ds, rp, rc = None, None, 100, 0
		for mg in summary:
			if mg['id'] == mg_id:
				ds = mg['displayState']
				rs = mg['displayRCStatus'] if 'displayRCStatus' in mg.keys() else None
				rp = mg['rebuildPerc']
				rc = mg['rcStatus']
				break

		print "MG Rebuild(%s)/Display states: %s/%s"%(rp, rs, ds)
		return rs, ds, rp, rc


	def rebuild_mg(self, mg_id):
		rs, ds, rp, rc = self.get_mg_state(mg_id)
		#if rs == 'Rebuilding': 
		'''
		if int(rp) != 100 or ds != 'Active':
			print "Rebuild not required!"
			return(0)

		'''
		if ds == 'Active':
			print "Already Active, not required to rebuild"
			return(0)

		if rc != 0:
			print "Rebuild not required!"
			return(0)

		print "\nInitiating rebuild..."
		data = {}

		api = "https://"+self._dict['ip']+"/api/v1.0/storage/mediagroups/%s/recover"%mg_id
		st, text = self.run_api(api, data, "POST")
		if st == -1:
			print "ERROR! Failed to initiate rebuild"
			return(1)

		time.sleep(5)
		return(0)


	def create_vols(self, mg_id, nvols, sz_per_vol, prefix="test", reserv=None):
		print "\nCreating Volume(s)"
		volume_ids = []
		for n in range(int(nvols)):
			name = "vol_" + prefix + "_" + str(n)
			reservation = random.choice([90, 50, 10, 40, 20, 30, 70, 100, 60]) if not reserv else reserv

			vid = self.create_volume(mg_id, sz_per_vol, name, reservation)
			if not vid:
				return(1)
			volume_ids.append(vid)
				
		print "VolumeIDs:", volume_ids
		return(volume_ids)


	def create_mg_vols(self):
		data = {}

		for n in range(1, int(self._dict['nmedia_grps'])+1):
			name = self.mg_key + str(n)
			zone = self._dict['media_grp%s'%(str(n))]['zone']
			raid_type = random.choice(self.avail_mg_types) 

			mg_id = self.create_media_group(name, zone, raid_type)
			if not mg_id:
				return(1)

			summary = self.get_given_parent_obj_info("storage", "mediagroups/%s/summary/"%mg_id)
			if not summary:
				return(1)

			mg_sz_gb = int(summary['configured']['available_config_storage_gb'])
			mg_sz_gb = int(mg_sz_gb) * 48 / 100	##To avoid over provisioning and for parallel testing

			nvol = self._dict['media_grp%s'%(str(n))]['nvolumes']
			if not nvol:
				continue
			sz_per_vol = mg_sz_gb / nvol

			vol_ids = self.create_vols(mg_id, nvol, sz_per_vol, 'mg%s'%str(n))
			if len(vol_ids) !=  nvol:
				return(1)

		if self.get_details():
			return(1)

		return(0)


	def medialist_of_mg(self, mgid):
		_temp = self.get_given_parent_obj_info("storage", "medias")
		
		m_list = [media['slot'] for media in _temp if 'mediaGroupId' in media and media['mediaGroupId'] == mgid]
		print "MediaList: ",m_list
		return(m_list)


	def get_details(self):
		print "\nReading MediaGroups:"
		data= {}
		api = "https://"+self._dict['ip']+"/api/v1.0/storage/mediagroups"
		st, allmgs = self.run_api(api, data)
		if st == -1:
			print "ERROR! No MGs found"
			return(1)
		
		used_zones = [self._dict['media_grp%s'%(str(n))]['zone'] for n in range(1, int(self._dict['nmedia_grps'])+1) ]
		print "Required Zones:",used_zones

		self._dict['mg_details'] = {}
		mg_details = {}
		for mg in allmgs: 
			det = {}
			if mg['zone'] not in used_zones:		##Going through MGs which are part of zones as in config file
				print "Skipping zone %s mediagroup(s) details"%mg['zone']
				continue

			det['mg_id'] = mg['id']
			det['zone'] = mg['zone']
			det['media_slots'] = self.medialist_of_mg(mg['id'])
			det['raid'] = mg['grpDefName']

			det['rebuild_type'] = 0
			if mg['grpDefName'] in ("RAID-6 (7+2)", "RAID-6 (16+2)"):
				det['rebuild_type'] = 1
			if mg['grpDefName'] in ("RAID-6 (6+2+1)", "RAID-6 (15+2+1)"):
				det['rebuild_type'] = 2
		
			summary = self.get_given_parent_obj_info("storage", "mediagroups/%s/summary/"%mg['id'])
			if summary == -1:
				return(1)

			mg_sz_gb = int(summary['configured']['available_config_storage_gb'])
			mg_sz_gb = int(mg_sz_gb) * 95 / 100	##To avoid over provisioning
			det['avail_size'] = mg_sz_gb

			summary = self.get_given_parent_obj_info("storage", "volumes/all")
			if summary == -1:
				return(1)

			det['vol_ids'], det['clone_ids'], det['snap_ids'] = [], [], []
			for vol in summary:
				if vol['mediaGrpId'] == mg['id']:
					if vol['displayType'] == 'Clone':
						det['clone_ids'].append(vol['id'])
					elif vol['displayType'] == 'Snapshot':
						det['snap_ids'].append(vol['id'])
					elif vol['displayType'] == 'Volume':
						det['vol_ids'].append(vol['id'])

			
			identity = mg['name'][len(self.mg_key):]
			det['ports'] = self._dict['media_grp%s'%(str(n))]['ports'] 

			mg_details[mg['name']] = det

		self._dict['mg_details'] = mg_details
		print self._dict['mg_details']

		if len(self._dict['mg_details'].keys()) != int(self._dict['nmedia_grps']):
			print "ERROR! Details populated doesn't match with required number of media groups"
			return(1)
		return(0)
		

	def assign_unassign_all_vols(self, objtype, op='assign'):
		if objtype not in ('volumes', 'snapshots', 'clones'):
			print "ERROR! Not an valid object"
			return(1)

		all_ports = []
		for mg in self._dict['mg_details'].keys():
			id_list = self._dict['mg_details'][mg]['vol_ids'] if objtype == 'volumes' else self._dict['mg_details'][mg]['cop_ids']
			if not id_list:
				continue
			ports = self._dict['mg_details'][mg]['ports']
			_ports = [p.split(':')[1] for p in ports]
			all_ports = list(set(ports) | set(all_ports))

			for _id in id_list:
				st = self.assign_object('volumes', _id, _ports, []) if op == 'assign' else self.unassign_object('volumes', _id)
				if st:
					return(1)

		self.get_port_ips(all_ports)
		self.port_ips = self._dict['ipdetails'].values()
		print self._dict['ipdetails']
		return(0)


	def delete_all_vols(self):
		for mg in self._dict['mg_details'].keys():
			vol_ids = self._dict['mg_details'][mg]['vol_ids']
			print "Deleting Volumes of mg:%s"%mg, vol_ids
			for _id in vol_ids:
				if self.del_storage_obj('volumes', _id):
					return(1)
		return(0)


	def cleanup(self):
		return((not self.assign_unassign_all_vols('volumes', 'unassign')) and (not self.delete_all_vols()) and (not self.del_media_group()))


	def setup(self):
		if self.create_mg_vols() or self.assign_unassign_all_vols('volumes', 'assign'):
			return(1)
		


