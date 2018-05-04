import requests,json,time,logging,multiprocessing,subprocess
from datetime import datetime

import sys
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def advance_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    formate = logging.Formatter('%(asctime)s : %(process)d : %(levelname)s : %(message)s')
    #filehandler
    fh = logging.FileHandler("myapp.txt")
    fh.setFormatter(formate)
    logger.addHandler(fh)
    #console handler
    sh = logging.StreamHandler()
    sh.setFormatter(formate)
    logger.addHandler(sh)
    return(logger)

logger = advance_logger()
jsession= None
xref = None
## importent inputs before run this script
CHASSIS_IP = '172.25.26.27'
CHASSIS_USER  = 'admin'
CHASSIS_PASS  = 'admin'
DOMAIN_NAME = 'localhost'
DOMAIN_TYPE = 'UNIXPWD'
CTRL_1_IP = "192.168.81.81"
CTRL_2_IP = "192.168.7.2"
CTRL_NO1 = 6
CTRL_NO2 = 10
ZONE = 4
MG_NAME = "z4"
NO_OF_VOLUMES = 2
HOST_IP = "172.25.26.208"
CTRL_IPS = "%s,%s"%(CTRL_1_IP,CTRL_2_IP)

id_dict = {}
nqn_dict = {}


'''
r = requests.get('https://api.github.com/events')
print r
print r.status_code
print r.encoding 
#print r.content
#print r.json()
'''

## basic logging
#format = "\n%(asctime)s %(process)d  %(message)s"
#logging.basicConfig(level=logging.INFO, format=format)
#logger = logging.getLogger(__file__)

def run(cmd, hostname=None, password=None, logcmd=1):

    if hostname :
        cmd_str = '/usr/bin/sshpass -p %s ssh root@%s '%(password, hostname)
        cmd_str += ' -o StrictHostKeyChecking=no '
        cmd_str += ' \" %s \" '%(cmd)
    else:
        cmd_str=cmd

    result = None
    logger.info('Executing Command %s'%cmd_str) if logcmd==1 else 0

    op=[]
    try:
        result = subprocess.Popen(cmd_str ,shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        result.wait()
        retcode = result.returncode
        stdout = result.stdout.readlines()
        msg = ('Done with Command '+cmd_str+' \n')
        msg += '{:>51}'.format('EXIT_CODE - %s\n')%retcode
        msg += '{:>44}'.format('STDOUT \n')
        if cmd_str.startswith('curl'):
            parsed = json.loads(stdout[0])
            msg+=json.dumps(parsed, indent=23, sort_keys=True)
            logger.info(msg+'\n') if logcmd==1 else 0
            return retcode, parsed
        else:
            for i in stdout:
                msg +=  ' '*43 +i
            logger.info(msg+'\n') if logcmd==1 else 0
        return retcode, stdout

    except Exception as E:
        logger.error('Stderr %s'%str(E)) if logcmd==1 else 0
        return 1,str(E)


def log_in():
    s = requests.session()
 #    r = s.post("https://" + CHASSIS_IP + "/api/v1.0/auth/login?password=" + CHASSIS_USER + "&username=" + CHASSIS_PASS,
 #               {"Accept": "application/json"}, verify=False)
    r = s.post("https://" + CHASSIS_IP + "/api/v1.0/auth/login?username=" + CHASSIS_USER + "&password=" + CHASSIS_PASS + "&domain_name=" + DOMAIN_NAME + "&domain_type="       +DOMAIN_TYPE,{"Accept": "application/json"}, verify=False)

    if(r.status_code!=200):
        print("LOGIN FAILED")
        assert(r.status_code!=0)
    jid = r.cookies["JSESSIONID"]
    xrf = r.cookies["XSRF-TOKEN"]
    #print jid,xrf
    return jid, xrf

def call_api(api_url, method, req_data=None):
    global jsession,xref
    if jsession == None or xref == None:
        jsession,xref = log_in()
    
    header = {"Content-Type": 'application/json;charset=utf-8', "XSRF-TOKEN": xref,
            "X-XSRF-TOKEN": xref, "Referer": "https://" + CHASSIS_IP + "/swagger-ui.html"}

    r = requests.request(method, api_url, headers=header, data=json.dumps(req_data),
                         cookies={"JSESSIONID": jsession}, verify=False)
    #assert(r.status_code ==200)
    return json.loads(r.text), str(r.status_code)


def get_chassis_info():
    url = "https://%s/pvl/v1.0/chassis/versioninfo"%(CHASSIS_IP)
    stdout,status =  call_api(url,'GET')
    #print json.dumps(stdout,indent=4)
    mgmt1 = {}
    mgmt2 = {}
    for ctlr in stdout:
        if ctlr['controllerId'] == 21 and ctlr['propId'] == 'Management Kernel Version':
            mgmt1['Management_Kernel_Version'] = ctlr['propValue']
        if ctlr['controllerId'] == 21 and ctlr['propId'] == 'Management Software Version':
            mgmt1['Management_Software_Version'] = ctlr['propValue']
        if ctlr['controllerId'] == 22 and ctlr['propId'] == 'Management Kernel Version':
            mgmt2['Management_Kernel_Version'] = ctlr['propValue']
        if ctlr['controllerId'] == 22 and ctlr['propId'] == 'Management Software Version':
            mgmt2['Management_Software_Version'] = ctlr['propValue']
    l={}
    l['MANAGEMENT_1'] = mgmt1
    l['MANAGEMENT_2'] = mgmt2
    print 'Build Info for chassis ------> %s' %CHASSIS_IP
    print json.dumps(l,indent=4)
    print '------------------------------------------------------------------------'
    print '\n'


def get_mediaGroup_info():
    #url = "https://%s/api/v1.0/storage/mediagroupdefinition"%(CHASSIS_IP)
    url = "https://%s/api/v1.0/storage/mediagroups"%(CHASSIS_IP)
    stdout,status =  call_api(url,'GET')
    #print json.dumps(stdout,indent=4)


def create_mg(mg_type,zone,name):
    url = "https://%s/api/v1.0/storage/mediagroups/create"%(CHASSIS_IP)
    data = {"media_group_type": mg_type,
            "media_zone": zone,
            "name": name
            } 
    stdout,status =  call_api(url,"POST",data)
    logger.info("Creating media group %s:%s:%s"%(mg_type,zone,name))
    ret = wait_till_task_completes(stdout["taskid"])
    if ret == 0:
        logger.info("Media group creation task(id=%s) completed sucessfully"%stdout["taskid"]) 

def delete_mg(mg_name):
    mg_id = get_object_id('mediagroup',mg_name)
    url = "https://%s/api/v1.0/storage/mediagroups/%s/delete"%(CHASSIS_IP,mg_id) 
    stdout,status =  call_api(url,"POST",{})
    logger.info("Deleting mediaGrup %s"%(mg_name))
    taskid = stdout["taskid"]
    wait_till_task_completes(taskid)
    
def get_object_id(object_type, object_name):
    url = "https://%s/api/v1.0/chassis/object_id?object_type=%s&object_name=%s"%(CHASSIS_IP,object_type,object_name)
    stdout,status =  call_api(url,"GET")
    #print json.dumps(stdout,indent=4)
    id = stdout["id"]
    return id 
    

def return_exact_time(time):
    #return '2018-03-13 10:05:07.000748617'
    return time.split('.')[0]

def wait_till_task_completes(task_id,string=''):
    tid = task_id[0] if type(task_id) == list else task_id
    url = "https://%s/api/v1.0/notification/tasks/%s"%(CHASSIS_IP, tid)
    count = 400
    FMT = '%Y-%m-%d %H:%M:%S'
    while 1:
        stdout , retcode = call_api(url,'GET')
        if stdout['displayState'] == "Completed" :
            start_time = return_exact_time(stdout['time'])
            end_time = return_exact_time(stdout['endTime'])
            tdelta = datetime.strptime(end_time, FMT) - datetime.strptime(start_time, FMT)
            logger.info(' %s Task completed in time %s '%(string, tdelta))
            return 0
        logger.info('Current task %s  state  %s '%(task_id,stdout['displayState']))
        if stdout['displayState'] == "Failed" :
            logger.info('Current task %s  state  %s is FAILED '%(task_id,stdout['displayState']))
            start_time = return_exact_time(stdout['time'])
            end_time = return_exact_time(stdout['endTime'])
            tdelta = datetime.strptime(end_time, FMT) - datetime.strptime(start_time, FMT)
            logger.info(' %s Task completed in time %s '%(string, tdelta))
            return 1
        time.sleep(30)

    
    
    
def drive_poweron(drive_num):
    url = "https://%s/api/v1.0/chassis/drives/poweron"%(CHASSIS_IP)
    data =  {
            'device_list' : [drive_num]
            }

    logger.info('powering on the drive %s'%drive_num)
    stdout , retcode = call_api(url,'POST', data)
    #error_check(stdout , retcode)
    taskid = stdout['taskid_list'] if stdout.has_key('taskid_list') else stdout['taskid']
    wait_till_task_completes(taskid)
    print stdout,retcode


def drive_poweroff(drive_num):
    url = "https://%s/api/v1.0/chassis/drives/poweroff"%(CHASSIS_IP)
    data =  {
            'device_list' : [drive_num]
            }
    logger.info('powering off the drive %s'%drive_num)
    stdout , retcode = call_api(url,'POST', data)
    #error_check(stdout , retcode)
    taskid = stdout['taskid_list'] if stdout.has_key('taskid_list') else stdout['taskid']
    wait_till_task_completes(taskid)
    print stdout,retcode

def drive_format(drive_num):
    url = "https://%s/api/v1.0/chassis/drives/format"%(CHASSIS_IP)
    data =  {
            'device_list' : [drive_num]
            }
    logger.info('formatting the drive %s'%drive_num)
    stdout , retcode = call_api(url,'POST', data)
def wait_till_task_completes(task_id):
    tid = task_id[0] if type(task_id) == list else task_id
    url = "https://%s/api/v1.0/notification/tasks/%s"%(CHASSIS_IP, tid)
    count = 200
    while 1:
        stdout , retcode = call_api(url,'GET')
       # print json.dumps(stdout,indent=4)
        if stdout['displayState'] == "Completed" :
            logger.info('Current task %s  state  %s '%(task_id,stdout['displayState']))
            return 0
        if stdout['displayState'] == "Failed" :
            logger.info('Current task %s  state  %s is FAILED '%(task_id,stdout['displayState']))
            return 1
        time.sleep(7)
    
def drive_poweron(drive_num):
    url = "https://%s/api/v1.0/chassis/drives/poweron"%(CHASSIS_IP)
    data =  {
            'device_list' : [drive_num]
            }

    logger.info('powering on the drive %s'%drive_num)
    stdout , retcode = call_api(url,'POST', data)
    #error_check(stdout , retcode)
    taskid = stdout['taskid_list'] if stdout.has_key('taskid_list') else stdout['taskid']
    wait_till_task_completes(taskid)
    print stdout,retcode


def drive_poweroff(drive_num):
    url = "https://%s/api/v1.0/chassis/drives/poweroff"%(CHASSIS_IP)
    data =  {
            'device_list' : [drive_num]
            }
    logger.info('powering off the drive %s'%drive_num)
    stdout , retcode = call_api(url,'POST', data)
    #error_check(stdout , retcode)
    taskid = stdout['taskid_list'] if stdout.has_key('taskid_list') else stdout['taskid']
    wait_till_task_completes(taskid)
    print stdout,retcode

def drive_format(drive_num):
    url = "https://%s/api/v1.0/chassis/drives/format"%(CHASSIS_IP)
    data =  {
            'device_list' : [drive_num]
            }
    logger.info('formatting the drive %s'%drive_num)
    stdout , retcode = call_api(url,'POST', data)
def wait_till_task_completes(task_id):
    tid = task_id[0] if type(task_id) == list else task_id
    url = "https://%s/api/v1.0/notification/tasks/%s"%(CHASSIS_IP, tid)
    count = 200
    while 1:
        stdout , retcode = call_api(url,'GET')
       # print json.dumps(stdout,indent=4)
        if stdout['displayState'] == "Completed" :
            logger.info('Current task %s  state  %s '%(task_id,stdout['displayState']))
            return 0
        if stdout['displayState'] == "Failed" :
            logger.info('Current task %s  state  %s is FAILED '%(task_id,stdout['displayState']))
            return 1
        time.sleep(7)
    
def drive_poweron(drive_num):
    url = "https://%s/api/v1.0/chassis/drives/poweron"%(CHASSIS_IP)
    data =  {
            'device_list' : [drive_num]
            }

    logger.info('powering on the drive %s'%drive_num)
    stdout , retcode = call_api(url,'POST', data)
    #error_check(stdout , retcode)
    taskid = stdout['taskid_list'] if stdout.has_key('taskid_list') else stdout['taskid']
    wait_till_task_completes(taskid)
    print stdout,retcode


def drive_poweroff(drive_num):
    url = "https://%s/api/v1.0/chassis/drives/poweroff"%(CHASSIS_IP)
    data =  {
            'device_list' : [drive_num]
            }
    logger.info('powering off the drive %s'%drive_num)
    stdout , retcode = call_api(url,'POST', data)
    #error_check(stdout , retcode)
    taskid = stdout['taskid_list'] if stdout.has_key('taskid_list') else stdout['taskid']
    wait_till_task_completes(taskid)
    print stdout,retcode

def drive_format(drive_num):
    url = "https://%s/api/v1.0/chassis/drives/format"%(CHASSIS_IP)
    data =  {
            'device_list' : [drive_num]
            }
    logger.info('formatting the drive %s'%drive_num)
    stdout , retcode = call_api(url,'POST', data)
    error_check(stdout , retcode)
    taskid = stdout['taskid_list'] if stdout.has_key('taskid_list') else stdout['taskid']
    wait_till_task_completes(taskid)
    print stdout,retcode


def get_port_id_volume(vol_name, ip):
    url = "https://%s/api/v1.0/storage/volumes/%s/networks"%(CHASSIS_IP,get_object_id('volume', vol_name))
    stdout,status =  call_api(url,'GET')
    #print type(stdout[0])
    for tmp_dict in stdout:
        if tmp_dict['ipaddr'] == ip:
            return tmp_dict['slot']


def get_volume_nqn(vol_name):
    if not nqn_dict.has_key(vol_name):
        url = "https://%s/api/v1.0/storage/volumes/all"%(CHASSIS_IP)
        stdout,status =  call_api(url,'GET')
        for tmp_dict in stdout:
            if tmp_dict['name'] == vol_name:
                nqn_dict[vol_name] = tmp_dict['serial']
                break
    return nqn_dict[vol_name]

def assign(vol_name, ip1,ip2=None):
    url = "https://%s/api/v1.0/storage/volumes/%s/assign"%(CHASSIS_IP,get_object_id('volume', vol_name))
    if ip1 and ip2:
        port1 = get_port_id_volume(vol_name, ip1)
        port2 = get_port_id_volume(vol_name, ip2)
        data = {
                "protocol": 1,
                "nwlist": [],
                "controllers": [],
                "ports": [port1,port2],
                "controller_id": -1,
                "hostnqn":[]
                }
        logger.info('Assigning volume %s to ip %s,%s'%(vol_name, ip1,ip2))
        stdout,retcode =  call_api(url,'POST', data)
        error_check(stdout , retcode)
        taskid = stdout['taskid_list'] if stdout.has_key('taskid_list') else stdout['taskid']
        wait_till_task_completes(taskid)
    else:
        port = get_port_id_volume(vol_name, ip1)
        data = {
                    "protocol": 1,
                    "nwlist": [],
                    "controllers": [],
                    "ports": [port],
                    "controller_id": -1,
                    "hostnqn":[]
              }   
        logger.info('Assigning volume %s to ip %s'%(vol_name, ip1))
        stdout,retcode =  call_api(url,'POST', data)
        #assert(stdout['error'] == 0)
        error_check(stdout , retcode)
        taskid = stdout['taskid_list'] if stdout.has_key('taskid_list') else stdout['taskid']
        wait_till_task_completes(taskid)

def unassign(vol_name):
    url = 'https://%s/api/v1.0/storage/volumes/unassign'%CHASSIS_IP
    data = {"volidlist":[get_object_id('volume', vol_name)]}
    logger.info('Ussigning volume %s '%(vol_name))
    stdout , retcode = call_api(url,'POST', data)
    error_check(stdout , retcode)
    taskid = stdout['taskid_list'] if stdout.has_key('taskid_list') else stdout['taskid']
    wait_till_task_completes(taskid)

def delete_vol(vol_name):
    url = "https://%s/api/v1.0/storage/volumes/delete"%CHASSIS_IP
    data = {"volidlist":[get_object_id('volume', vol_name)]}
    logger.info('Deleting volume %s '%(vol_name))
    stdout , retcode = call_api(url,'POST', data)
    error_check(stdout , retcode)
    taskid = stdout['taskid_list'] if stdout.has_key('taskid_list') else stdout['taskid']
    wait_till_task_completes(taskid)
    id_dict.pop(vol_name, None)

def create_snapshot(snap_name, vol_name):
    url = "https://%s/api/v1.0/storage/snapshots/create"%CHASSIS_IP
    #vol_id = get_object_id('volume',vol_name)
    vol_id = get_object_id('volume',vol_name)
    data = {
                "name": snap_name,
                "type": "Snapshot",
                "parent_id": vol_id,
        }

    logger.info('Creating snapshot volume %s  snapshot %s '%(vol_name,snap_name))
    stdout , retcode = call_api(url,'POST', data)
    error_check(stdout , retcode)
    taskid = stdout['taskid_list'] if stdout.has_key('taskid_list') else stdout['taskid']
    wait_till_task_completes(taskid)

def create_clone(clone_name, snap_name, reservation):
    url = "https://%s/api/v1.0/storage/snapshots/create"%CHASSIS_IP
    data =  {
        "name": clone_name,
        "type": "Clone",
        "parent_id": get_object_id('volume',snap_name),
        "reservation":str(reservation)
    }
    logger.info('Creating clone snapshot %s clone %s'%(snap_name,clone_name))
    stdout , retcode = call_api(url,'POST', data)
    error_check(stdout , retcode)
    taskid = stdout['taskid_list'] if stdout.has_key('taskid_list') else stdout['taskid']
    wait_till_task_completes(taskid)

def delete_copy(copy_name):
    url = "https://%s/api/v1.0/storage/snapshots/delete"%CHASSIS_IP
    data = {"snapshotidlist":[get_object_id('volume',copy_name)]}
    logger.info('Deleting copy %s'%copy_name)
    stdout , retcode = call_api(url,'POST', data)
    error_check(stdout , retcode)
    taskid = stdout['taskid_list'] if stdout.has_key('taskid_list') else stdout['taskid']
    wait_till_task_completes(taskid)
    id_dict.pop(copy_name, None)




def create_vol(size, stripe , name, reservation, md_grp, flavor):
    #retcode,stdout = call_curl_api('GET', 'https://%s/api/v1.0/storage/mediagroups'%CHASSIS_IP)
    id_md = get_object_id('mediagroup', md_grp)

    #for i in range(0,len(stdout)):
    #   print 'media group name',stdout[i]['name']
    data = {
                                "size": size,
                                "strpsize": stripe,
                                "name": name,
                                "media_group_id": id_md,
                                "reservation": reservation,
                                "flavor": flavor,
                                "rw": 85,
                                "wl": "Analytics"
        }

    url = 'https://%s/api/v1.0/storage/volumes/create'%CHASSIS_IP
    logger.info('creating volume %s with param %s'%(name,data))
    stdout , retcode = call_api(url,'POST', data)
    error_check(stdout , retcode)
    taskid = stdout['taskid_list'] if stdout.has_key('taskid_list') else stdout['taskid']
    wait_till_task_completes(taskid)
    id_dict[name] = get_object_id('volume',name)
    #call__api('POST', url , data)

def error_check(stdout, retcode):
    if (stdout['error'] != 0):
        print stdout,retcode
    #assert(stdout['error'] == 0)

def connect_host(ctrl_ip, host, vol_name):
    for ip in ctrl_ip.split(','):
        cmd =  '/usr/sbin/nvme connect -t rdma  -a %s -s 4420 -n %s'%(ip, get_volume_nqn(vol_name))
        run(cmd, host, 'test')

def disconnect_vol(host, vol_name):
    cmd = "/usr/sbin/nvme disconnect -n %s"%get_volume_nqn(vol_name)
    run(cmd, host, 'test')
    run(cmd, host, 'test')

def get_dev_name(host, vol_name,mpath=None):
    if mpath:
        cmd = "/usr/sbin/nvme list |grep %s |grep -i mp|awk '{print $1}'"%get_volume_nqn(vol_name)
        stdout = run(cmd, host, 'test')
        return stdout[1][0].rstrip()
    else:
        cmd = "/usr/sbin/nvme list |grep %s |awk \'{print \$1}\'" %get_volume_nqn(vol_name)
        stdout = run(cmd, host, 'test')
        return stdout[1][0].rstrip()

def multi_assign(vol_name, ip_list):

    controller_ports = list()

    for ip in ip_list.split(','):
        vol_net = dict()
        vol_net  = get_controller_network_details(vol_name, ip)
        controller_ports.append(vol_net['slot'])
    print controller_ports

    data = {
             "hostnqn": [ ],
             "ports": ["40g-2/4", "40g-3/4"]
        }

    url = 'https://%s/api/v1.0/storage/volumes/%s/assign'%(CHASSIS_IP, get_object_id('volume', vol_name))
    logger.info('assigning volume % to ports %s'%(vol_name, ip_list))
    stdout , retcode = call_api(url,'POST', data)
    error_check(stdout , retcode)
    taskid = stdout['taskid_list'] if stdout.has_key('taskid_list') else stdout['taskid']
    wait_till_task_completes(taskid)


def get_controller_network_details(vol_name, ctlr_ip):
    url = "https://%s/api/v1.0/storage/volumes/%s/networks"%(CHASSIS_IP,get_object_id('volume', vol_name))
    stdout , retcode = call_api(url,'GET')
    #print(stdout, retcode)
    #error_check(stdout , retcode)
    for tmp_dict in stdout:
        if tmp_dict['ipaddr'] == ctlr_ip:
            return tmp_dict


def get_md_info(md_grp):
    url = "https://%s/api/v1.0/storage/mediagroups"%(CHASSIS_IP)
    stdout , retcode = call_api(url,'GET')
    for m in stdout:
        if m["name"] == md_grp:
            return  m

def rebuild_media_grp(md_grp):
    url = "https://%s/api/v1.0/storage/mediagroups/%s/recover"%(CHASSIS_IP,get_object_id('mediagroup', md_grp))
    data = {"grp": get_md_info(md_grp),"priority": "APPLICATION"}
    print 'calling rebuild '
    stdout , retcode = call_api(url,'POST', data)
    print stdout , retcode
    if stdout['error'] != 0 :
        time.sleep(60)
        print 'calling recursaviely rebuild '
        rebuild_media_grp(md_grp)
    error_check(stdout , retcode)
    taskid = stdout['taskid_list'] if stdout.has_key('taskid_list') else stdout['taskid']
    logger.info('waiting for 180 sec')
    time.sleep(180)
    ret_stat = wait_till_task_completes(taskid)
    if ret_stat == 1 :
        print 'calling recursaviely rebuild '
        rebuild_media_grp(md_grp)

def check_media_on_chassis():
    url = "https://%s/api/v1.0/storage/medias"%(CHASSIS_IP)
    stdout,stderr = call_api(url,'GET')
    return(stdout,stderr)


def do_io(host, vol_name, size,timebase,runtime, pattern=None,mpath=None):
    if mpath:
        dev_name = get_dev_name(HOST_IP, vol_name,mpath)
        logger.info("Starting FIO load on %s"%dev_name)
        cmd ='fio --ioengine=libaio --invalidate=1 --iodepth=64 --verify_dump=0 --error_dump=1 --exitall_on_error=1 --direct=1 --atomic=1 --group_reporting --do_verify=0 --time_based --size=%s  --random_generator=tausworthe64 --offset=0 --bs=8k --rw=write --name=1 --filename=%s --verify_pattern=0x%s --time_based=%s --runtime=%s' %( size,dev_name,pattern,timebase,runtime)

        run(cmd, HOST_IP , 'test')
    else:
        dev_name = get_dev_name(HOST_IP, vol_name)
        logger.info("Starting FIO load on %s"%dev_name)
        cmd ='fio --ioengine=libaio --invalidate=1 --iodepth=64 --verify_dump=0 --error_dump=1 --exitall_on_error=1 --direct=1 --atomic=1 --group_reporting --do_verify=0 --time_based --size=%s  --random_generator=tausworthe64 --offset=0 --bs=8k --rw=write --name=1 --filename=%s --verify_pattern=0x%s --time_based=%s --runtime=%s' %( size,dev_name,pattern,timebase,runtime)
        run(cmd, HOST_IP , 'test')

def ctrl_poweroff(ctrl_slot):
    url = "https://%s/api/v1.0/chassis/controllers/poweroff"%(CHASSIS_IP)
    data = {
            "device_list": [ctrl_slot]
            }
    stdout,retcode = call_api(url,'POST',data)
    logger.info("controller %s is getting powered Off"%ctrl_slot)
    taskid = stdout['taskid_list'] if stdout.has_key('taskid_list') else stdout['taskid']
    wait_till_task_completes(taskid)
    #print json.dumps(stdout,indent=4)

def ctrl_poweron(ctrl_slot):
    url = "https://%s/api/v1.0/chassis/controllers/poweron"%(CHASSIS_IP)
    data = {
            "device_list": [ctrl_slot]
            }
    stdout,retcode = call_api(url,'POST',data)
    logger.info("controller %s is getting powered On"%ctrl_slot)
    taskid = stdout['taskid_list'] if stdout.has_key('taskid_list') else stdout['taskid']
    wait_till_task_completes(taskid)
    #print json.dumps(stdout,indent=4)


#get_chassis_info()
#get_mediaGroup_info()
#create_mg("RAID-6 (7+2)",4,"mg123")
#delete_mg("mg123")

#create_vol('100', '4','vol1', str(100), MG_NAME, 'INSANE')

if __name__=='__main__':
    vol_list = []  
    def create_assign_vol(size, stripe , name, reservation, md_grp, flavor,IP1,IP2=None):
        create_vol(size, stripe , name, reservation, md_grp, flavor)
        #create_vol('100', '4',vol, str(100), MG_NAME, 'INSANE') 
        assign(name,IP1,IP2)
    
    def multiproc(no):
        volname= 'ML_TV'
        for i in range(no):
            vol = volname+"_"+str(i)
            #p = multiprocessing.Process(target=create_assign_vol,args=('300', '4',vol, str(70), MG_NAME, 'INSANE',CTRL_1_IP,CTRL_2_IP))
            p = multiprocessing.Process(target=create_assign_vol,args=('100', '4',vol, str(70), MG_NAME, 'INSANE',CTRL_1_IP))
            p.start()
            p.join()
            vol_list.append(vol)
   
    # Starting the test here 
    multiproc(NO_OF_VOLUMES)
   ## unassigning and delteing the volumes 
    for volname in vol_list:
        unassign(volname)
	time.sleep(5)
	logger.info("volument is getting unassigned,sleeping for 5 sec ") 
    for volname in vol_list:
	delete_vol(volname)
	time.sleep(5)
	logger.info("volument is getting deleted,sleeping for 5 sec ") 

    
