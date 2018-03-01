import ast
import json
import multiprocessing
import time

import pprint
import logging
from time import sleep
import subprocess
import random
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

format = "\n%(asctime)s %(process)d  %(message)s";
logging.basicConfig(level=logging.INFO, format=format)
logger = logging.getLogger(__file__);
CHASSIS_IP = '172.25.26.28'
CHASSIS_USER  = 'admin'
CHASSIS_PASS  = 'admin'

HOST_IP = '172.25.26.86'
HOST_PASS = 'test'
jsession=None
xref=None

id_dict = {}
nqn_dict = {}

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
        #print stdout
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
    
        #print type(stdout)
    except Exception as E:
        logger.error('Stderr %s'%str(E)) if logcmd==1 else 0
        return 1,str(E)

def log_in():
    cmd = 'curl -k -X POST -H \'Accept-Encoding: gzip, deflate\' -H \'Accept: */*\' -H \'Connection: keep-alive\' -H \'Content-Length: 25\' -H \'Content-Type: application/x-www-form-urlencodead\' -H \'User-Agent: python-requests/2.13.0\' -d \'Accept=application/json\' \'https://%s/api/v1.0/auth/login?password=%s&username=%s\''%(CHASSIS_IP, CHASSIS_USER, CHASSIS_PASS)
    s = requests.session()
    r = s.post("https://" + CHASSIS_IP + "/api/v1.0/auth/login?password=" + CHASSIS_USER + "&username=" + CHASSIS_PASS,
               {"Accept": "application/json"}, verify=False)
    if (r.status_code != 200):
        logger.debug("LOG IN FAILED")
        assert(r.status_code != 200)
    jid = r.cookies["JSESSIONID"]
    xrf = r.cookies["XSRF-TOKEN"]
    #logger.info("JSESSIONID:" + jid)
    #logger.info("COOKIES:" + xrf)
    return jid, xrf


def call_curl_api(method, api, data="'None'"):
    global jsession, xref

    if jsession ==  None or xref == None:
        jsession, xref= log_in()
    curl_cmd = 'curl --fail --silent --show-error -k -X %s -H \'Accept-Encoding: identity, deflate\' -H \'Accept: */*\' -H \'Connection: keep-alive\' -H \'Content-Length: 174\' -H \'Content-Type: application/json;charset=UTF-8\' -H \'Cookie: JSESSIONID=%s\' -H \'Referer: https://%s/swagger-ui.html\' -H \'User-Agent: python-requests/2.13.0\' -H \'X-XSRF-TOKEN: %s\' -H \'XSRF-TOKEN: %s\' -d '%(method, jsession, CHASSIS_IP, xref, xref)
    if data == "'None'" :
        curl_cmd += data +' \'' + api +'\''
    else:
        curl_cmd += '"' + str(data) + '" \''  + api +'\''

    return run(curl_cmd,)

def call_api(api_url, method, req_data=None):
    global jsession, xref
    if jsession ==  None or xref == None:
        jsession, xref= log_in()

    """ This actually executes the api and returns the response a JSON response"""
    header = {"Content-Type": 'application/json;charset=utf-8', "XSRF-TOKEN": xref,
              "X-XSRF-TOKEN": xref, "Referer": "https://" + CHASSIS_IP + "/swagger-ui.html"}
    '''
    logger.debug("Header:" + str(header))
    logger.debug("Method:" + method)
    logger.debug("API url:" + api_url)
    logger.debug("Requested Data:" + str(req_data))
    '''

    r = requests.request(method, api_url, headers=header, data=json.dumps(req_data),
                         cookies={"JSESSIONID": jsession}, verify=False)
    #print(curlify.to_curl(r.request))
    #print(curlify.to_curl(r.request))
    #print(curlify.to_curl(r.request))
    assert(r.status_code ==200)
    #print r.text, r.status_code
    return json.loads(r.text), str(r.status_code)

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
	print type(stdout[0])
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


def get_object_id(object_type, object_name):

    if not id_dict.has_key(object_name):
        url = 'https://%s/api/v1.0/chassis/object_id?object_type=%s&object_name=%s'%(CHASSIS_IP,object_type, object_name)
        #retcode, stdout = call_curl_api('GET', url)
        stdout,status =  call_api(url,'GET')
        #print stdout['id'].decode('utf-8')

        id_dict[object_name] = stdout['id'].decode('utf-8')
    return id_dict[object_name]

def assign(vol_name, ip):
    port = get_port_id_volume(vol_name, ip)
    url = "https://%s/api/v1.0/storage/volumes/%s/assign"%(CHASSIS_IP,get_object_id('volume', vol_name))
    data = {
				"protocol": 1,
				"nwlist": [],
				"controllers": [],
				"ports": [port],
				"controller_id": -1,
				"hostnqn":[]
			}
    logger.info('Assigning volume %s to ip %s'%(vol_name, ip))
    stdout,retcode =  call_api(url,'POST', data)
    #assert(stdout['error'] == 0)
    error_check(stdout , retcode)
    taskid = stdout['taskid_list'] if stdout.has_key('taskid_list') else stdout['taskid']
    wait_till_task_completes(taskid)


def create_media_group(zone,md_type, name):
    url = "https://%s/api/v1.0/storage/mediagroups/create"%(CHASSIS_IP)
    data = { 
                "media_zone":"%s"%(zone),
                "media_group_type":"%s"%(md_type),
                "name":"%s"%(name)
           } 
    logger.info('creating media group %s  %s %s '%(zone,md_type, name))
    stdout,retcode =  call_api(url,'POST', data)
    error_check(stdout , retcode)
    taskid = stdout['taskid_list'] if stdout.has_key('taskid_list') else stdout['taskid']
    wait_till_task_completes(taskid)

def delete_media_group(name):
    md_id = get_object_id('mediagroup', name)
    print md_id
    url = "https://%s/api/v1.0/storage/mediagroups/%s/delete"%(CHASSIS_IP, md_id)
    logger.info('deleting media group %s  '%(name))
    stdout,retcode =  call_api(url,'POST',{})
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
    print stdout,retcode
    

def wait_till_task_completes(task_id):
    tid = task_id[0] if type(task_id) == list else task_id
    url = "https://%s/api/v1.0/notification/tasks/%s"%(CHASSIS_IP, tid)
    count = 200
    while 1:
        stdout , retcode = call_api(url,'GET')
        if stdout['displayState'] == "Completed" :
            return 0
        logger.info('Current task %s  state  %s '%(task_id,stdout['displayState']))
        if stdout['displayState'] == "Failed" :
            logger.info('Current task %s  state  %s is FAILED '%(task_id,stdout['displayState']))
            return 1
        time.sleep(5)

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

    logger.info('Creating snapshot volume %s  snapshot '%(vol_name,snap_name))
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
    assert(stdout['error'] == 0)

def connect_host(ctrl_ip, host, vol_name):
    for ip in ctrl_ip.split(','):
        cmd =  '/usr/sbin/nvme connect -t rdma  -a %s -s 1032 -n %s'%(ip, get_volume_nqn(vol_name)) 
        run(cmd, host, 'test')
def disconnect_vol(host, vol_name):
    cmd = "/usr/sbin/nvme disconnect -n %s"%get_volume_nqn(vol_name)
    run(cmd, host, 'test')
    run(cmd, host, 'test')

def get_dev_name(host, vol_name):
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
    


def do_io(host, vol_name, size, pattern):
    dev_name = get_dev_name(HOST_IP, vol_name)
    cmd ='fio --ioengine=libaio --invalidate=1 --iodepth=64 --verify_dump=1 --error_dump=1 --exitall_on_error=1 --direct=1 --atomic=1 --group_reporting --do_verify=1 --time_based --size=%s  --random_generator=tausworthe64 --offset=0 --bs=4k --rw=write --name=1 --filename=%s --verify_pattern=0x%s' %( size,dev_name,  pattern)

    run(cmd, HOST_IP , 'test')

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
        




'''
for i in range(1,20000):
        create_vol('2000', '4','vol1', str(100), 'L_MD_GRP', 'INSANE') 
        get_port_id_volume('vol1','192.168.10.14')
        assign('vol1','192.168.10.14')
        unassign('vol1')
        delete_vol('vol1')
        print '=========================Done with round %s ================' i
#get_object_id('mediagroup', 'L_MD_GRP')


vol= 'Pune_1'
create_vol('100', '4',vol, str(10), 'L_MD_GRP', 'INSANE') 
#get_port_id_volume(vol,'192.168.10.14')
assign(vol,'192.168.10.14')
create_snapshot('snap2', vol)
create_clone('c2', 'snap2', '100')
get_volume_nqn(vol)
get_volume_nqn('snap2')
get_volume_nqn('c2')
delete_copy('c2')
delete_copy('snap2')
unassign(vol)
delete_vol(vol)

#print get_controller_network_details('vol2','192.168.10.12')
#multi_assign('vol2','192.168.10.12,192.168.10.13')
#ctrl_ip, host, vol_name
#connect_host('192.168.10.12',HOST_IP, 'vol2')
#drive_poweroff('21:22')
#drive_poweron(21)
#drive_poweron(22)
#ief exec_api():



#test case

vol_name = 'Pune_1'
create_vol('100', '4',vol_name, str(10), 'L_MD_GRP', 'INSANE')
assign(vol_name,'192.168.10.14')
connect_host('192.168.10.14',HOST_IP, vol_name)
do_io

dev_name = get_dev_name(HOST_IP, vol_name)
for i in range(1,11):
    pattern=1000+i
    snap_name = ('%s_S_0x%s')%(vol_name,pattern)
    clone_name = ('%s_C_0x%s')%(vol_name,pattern)
    cmd ='fio --ioengine=libaio --invalidate=1 --iodepth=64 --verify_dump=1 --error_dump=1 --exitall_on_error=1 --direct=1 --atomic=1 --group_reporting --do_verify=1 --time_based --size=10g  --random_generator=tausworthe64 --offset=0 --bssplit=4k/20:16k/20:32k/20:64k/20:128k/20 --rw=write --name=1 --filename=%s --verify_pattern=0x%s' %( dev_name, pattern)

    run(cmd, HOST_IP , 'test')

    create_snapshot(snap_name, vol_name)
    assign(snap_name,'192.168.10.12')
    #create_clone(clone_name,snap_name,str(10*i))
    #assign(clone_name,'192.168.10.13')



for i in range(1,11):
    pattern=1000+i
    snap_name = ('%s_S_0x%s')%(vol_name,pattern)
    clone_name = ('%s_C_0x%s')%(vol_name,pattern)
    connect_host('192.168.10.12',HOST_IP, snap_name)
    dev_name = get_dev_name(HOST_IP, snap_name)
    cmd ='fio --ioengine=libaio --invalidate=1 --iodepth=64 --verify_dump=1 --error_dump=1 --exitall_on_error=1 --direct=1 --atomic=1 --group_reporting --do_verify=1 --size=10g  --random_generator=tausworthe64 --offset=0 --bssplit=4k/20:16k/20:32k/20:64k/20:128k/20 --rw=read --name=1 --filename=%s --verify_pattern=0x%s' %( dev_name, pattern)

    run(cmd, HOST_IP , 'test')

    cmd = 'pnvm -disconnectall'
    run(cmd, HOST_IP , 'test')
    #create_clone(clone_name,snap_name,str(10*i))
    #assign(clone_name,'192.168.10.13')


for k in range(0,40):
    ctrl = ['192.168.10.12','192.168.10.13','192.168.10.14']
    ip = ctrl[random.randint(0,2)]
    print ip 
    p=[]
    for i in range(1,6):
        print 'Pune_%s'%i
        p.append(multiprocessing.Process(target=assign, args=('Pune_%s'%i, ip,)))
    for j in range(0,len(p)):
        p[j].start()
    for j in range(0,len(p)):
        if p[j].is_alive():
            p[j].join()


    print 'sleeping'
    sleep(200)

    p=[]
    for i in range(1,6):
        print 'Pune_%s'%i
        p.append(multiprocessing.Process(target=unassign, args=('Pune_%s'%i,)))
    for j in range(0,len(p)):
        p[j].start()
    for j in range(0,len(p)):
        if p[j].is_alive():
            p[j].join()

    sleep(10)

def keep_rebuild_running():
    #drv_list = [23,28,29,30,31,32,33,34,35]
    drv_list = [24,25,26,27,28,29,30]
    for d in drv_list:
        drive_poweroff(d)
        time.sleep(20)
        drive_poweron(d)
        time.sleep(60)
        rebuild_media_grp('L_MD_GRP')
        time.sleep(30)


#"RAID-0 (9+0)"
#"RAID-6 (7+2)"
#create_media_group(1,"RAID-0 (9+0)","L_MD_GRP")
#delete_media_group("L_MD_GRP")

vol_name = 'VOL1'
i=1
md_def = ["RAID-0 (9+0)", "RAID-6 (7+2)", "RAID-6 (6+2+1)"]

d1=24
d2=25
while True:
        drive_poweroff(d1)
        drive_poweroff(d2)
        time.sleep(20)
        drive_poweron(d1)
        drive_poweron(d2)
        time.sleep(60)
        rebuild_media_grp('L_MD_GRP')
        time.sleep(30)
        i+=1
        logger.info('ROUND completed ======================= %s'%i)



'''

