import requests,json,time,logging,multiprocessing


## basic logging 
#format = "\n%(asctime)s %(process)d  %(message)s";
#logging.basicConfig(level=logging.INFO, format=format)
#logger = logging.getLogger(__file__);

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
CHASSIS_IP = '172.25.26.9'
CHASSIS_USER  = 'admin'
CHASSIS_PASS  = 'admin'
jsession= None
xref = None

'''
r = requests.get('https://api.github.com/events')
print r
print r.status_code
print r.encoding 
#print r.content
#print r.json()
'''

def log_in():
    s = requests.session()
    r = s.post("https://" + CHASSIS_IP + "/api/v1.0/auth/login?password=" + CHASSIS_USER + "&username=" + CHASSIS_PASS,
               {"Accept": "application/json"}, verify=False)
    if(r.status_code!=200):
        print("LOGIN FAILED")
        assert(r.status_code!=0)
    jid = r.cookies["JSESSIONID"]
    xrf = r.cookies["XSRF-TOKEN"]
    print jid
    print xrf
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
    print json.dumps(stdout,indent=4)


def create_mg(mg_type,zone,name):
    url = "https://%s/api/v1.0/storage/mediagroups/create"%(CHASSIS_IP)
    data = {"media_group_type": mg_type,
            "media_zone": zone,
            "name": name
            } 
    stdout,status =  call_api(url,"POST",data)
    print json.dumps(stdout,indent=4)
    print(status)
    ret = wait_till_task_completes(stdout["taskid"])
    if ret == 0:
        print("Media group creation task(id=%s) completed sucessfully"%stdout["taskid"]) 

def delete_mg(mg_name):
    mg_id = get_object_id('mediagroup',mg_name)
    print("MG ID is ---%s"%mg_id)
    url = "https://%s/api/v1.0/storage/mediagroups/%s/delete"%(CHASSIS_IP,mg_id) 
    stdout,status =  call_api(url,"POST",{})
    print json.dumps(stdout,indent=4)
    taskid = stdout["taskid"]
    wait_till_task_completes(taskid)
    
def get_object_id(object_type, object_name):
    url = "https://%s/api/v1.0/chassis/object_id?object_type=%s&object_name=%s"%(CHASSIS_IP,object_type,object_name)
    stdout,status =  call_api(url,"GET")
    id = stdout["id"]
    return id 
    
def wait_till_task_completes(task_id):
    tid = task_id[0] if type(task_id) == list else task_id
    url = "https://%s/api/v1.0/notification/tasks/%s"%(CHASSIS_IP, tid)
    count = 200
    while 1:
        stdout , retcode = call_api(url,'GET')
        print json.dumps(stdout,indent=4)
        if stdout['displayState'] == "Completed" :
            print('Current task %s  state  %s '%(task_id,stdout['displayState']))
            return 0
        if stdout['displayState'] == "Failed" :
            print('Current task %s  state  %s is FAILED '%(task_id,stdout['displayState']))
            return 1
        time.sleep(7)
    


#get_chassis_info()
#get_mediaGroup_info()
create_mg("RAID-6 (7+2)",4,"mg123")
delete_mg("mg123")

