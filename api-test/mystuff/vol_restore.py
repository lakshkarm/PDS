#!/usr/bin/python -B
import random
import inspect
import logging
import json
import pvlclient
import time
import requests
from os import environ
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from nose.plugins.attrib import attr

from lib.misc.PVLLogger import PvltLogger
from lib.storage.MEDIAGROUP import MediaGroupOps
from lib.storage.VOLUME import VolumeOps
from lib.storage.SNAPSHOT import SnapShotOps
from lib.storage.CLONE import CloneOps
from lib.ioutils.HOSTUTILS import HostOps
from lib.ioutils.FIOUTILS import FioUtils
from lib.system.DRIVEUTILS import * 

from lib.system.CONTROLLER import (
    get_single_ctlr_port,
    get_two_port_diff_ctlr,
    get_dual_port_ctlr
)

from lib.system.DRIVEUTILS import (
    get_active_drive_count
    )

from config.ENV import (
    CHASSIS_IP,
    CHASSIS_USER,
    CHASSIS_PASS,
    ZONE,
    MEDIA_GROUP_TYPE,
    MEDIA_GROUP_NAME,
    HOST,
    VOL_SIZE,
    FLAVOR,
    VOL_PREFIX,
    VOL_RES,
    FILE_SYSTEM

)

from lib.system.DRIVEUTILS import (
    get_active_drive_count,
    power_off_drive,
    power_on_drive
    )
# import some extra mofules 
import multiprocessing,time

def wait_till_task_completes(task_id):
    logger = log.logger
    pvlLibHandle = pvlclient.New("2.0",CHASSIS_IP,logger=logger)
    result = pvlLibHandle.auth.login(user=CHASSIS_USER,password=CHASSIS_PASS)

    tid = task_id[0] if type(task_id) == list else task_id
    status = pvlLibHandle.system.generic_api('GET', '/notification/tasks/%s'%tid)
    count = 200
    while 1:
        stdout = pvlLibHandle.system.generic_api('GET', '/notification/tasks/%s'%tid)
       # print json.dumps(stdout,indent=4)
        if stdout['displayState'] == "Completed" :
            logger.info('Current task %s  state  %s '%(task_id,stdout['displayState']))
            return 0
        if stdout['displayState'] == "Failed" :
            logger.info('Current task %s  state  %s is FAILED '%(task_id,stdout['displayState']))
            return 1
        time.sleep(7)

def list_existing_obj(MG_NAME):
    vol_list = []
    snap_list  = []
    clone_list = []
    #logger = log.logger
    pvlLibHandle = pvlclient.New("2.0",CHASSIS_IP,logger=logger)
    result = pvlLibHandle.auth.login(user=CHASSIS_USER,password=CHASSIS_PASS)
    stdout = pvlLibHandle.system.generic_api('GET', '/storage/volumes/all')
    #url = "https://%s/api/v1.0/storage/volumes/all"%(CHASSIS_IP)
    print  stdout
    for i in stdout:
        if i["mediaGrpName"] == MG_NAME and i["displayType"] == "Volume":
            vol_name = i["name"]
            volume = vol_name.encode('ascii')
            vol_list.append(volume)
        elif i["mediaGrpName"] == MG_NAME and i["displayType"] ==  "Snapshot":
            snap_name = i["name"]
            snapshot = snap_name.encode('ascii')
            snap_list.append(snapshot)
        elif i["mediaGrpName"] == MG_NAME and i["displayType"] == "Clone":
            clone_name = i["name"]
            clone = clone_name.encode('ascii')
            clone_list.append(clone)
    return (vol_list,snap_list,clone_list)


def pds_vol_restore_sanity():
    host = HostOps(HOST[0])
    fio = FioUtils()
    # give function name as log file name
    log = PvltLogger("Volume_restore",'INFO')
    logger = log.logger
    name = MEDIA_GROUP_NAME
    pvlLibHandle = pvlclient.New("2.0",CHASSIS_IP,logger=logger)
    result = pvlLibHandle.auth.login(user=CHASSIS_USER,password=CHASSIS_PASS)
    ## creating mediaGroup
    drv_cnt = get_active_drive_count(ZONE,pvlLibHandle)
    logger.info(ZONE)
    logger.info(drv_cnt)
    if drv_cnt < 9 :
        logger.error('Not sufficient drives active drive count=%s'%drv_cnt)
        #assert(drv_cnt > 8 )

    # take it from config 
    md_type = 'RAID-0 (18+0)' if drv_cnt == 18 else 'RAID-6 (7+2)'
    logger.info("Creating a MediaGroup")
    md = MediaGroupOps(pvlLibHandle, name, ZONE, md_type,create=False)
    media_group = md
    assert(md != None)
    ## creaing volumes 
    logger.info("Creating voluems")
    vol_list = []
    for i in range(1):
        # dont use + fro contact use %
        volname = str(VOL_PREFIX )+str("_")+str(i)
        volname = '%s_%s'%(VOL_PREFIX ,i)
        vol=VolumeOps(md=media_group,name=volname,size=VOL_SIZE,vol_res=VOL_RES,flavor=FLAVOR,create=False)
        vol_list.append(vol)
    #Creating a snapshot
    snap_name = "s1" 
    logger.info("Creating a snapshot : %s"%snap_name)
    snapshot = SnapShotOps(snap_name,volobj=vol_list[0],create=False)
    assert(snapshot != None)


################################ 1 Vol restore for unassigned volume  
        # Restore the vol using its snapshot
    snap_id = snapshot.snap_id    
    print snap_id
    logger.info("Running vol_restore using following snaphost : %s"%snap_name)
    status = pvlLibHandle.system.generic_api('POST', '/storage/snapshots/%s/restore'%snap_id)
    assert(status != 200)
    time.sleep(60)
    print("1 Vol restore for unassigned volume: PASS")

################################ 2 Vol restore after assign volume
    ports = get_two_port_diff_ctlr(ZONE)
    logger.info("Assigning vols ")
    assign = [v.assign_volume(ports,hostnqn=[]) for v in vol_list]
    logger.info("Running vol_restore using following snaphost : %s"%snap_name)
    status = pvlLibHandle.system.generic_api('POST', '/storage/snapshots/%s/restore'%snap_id)
    assert(status != 200)
    time.sleep(60)
    print("2 Vol restore after assign volume:PASS")

 ################################## delete s1 and its child snapshot 
     #vol,snap_list,clone_list = list_existing_obj(md.name)
     #for snap in snap_list:
         #snap_to_delete = SnapShotOps(snap,volobj=vol_list[0])
         #if snap != snap_name:
             #status = snap_to_delete.delete_snapshot
             #assert(status != None)
    #result = pvlLibHandle.storage.get_snapshot
    #print result
    #print json.dumps(result,indent=4)
################################## 3. Vol restore after 5% IO on the vol
    status = [host.connect_volume(v) for v in vol_list]
    assert(status!=0)
    time.sleep(5)
        #stert fio on all the volumes 
    logger.info("Starting write on the vol-seq_write")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write(vol_list, host, kwargs)
        # Taking snaphost 
    snap_name = "s2" 
    logger.info("Taking snapshot :%s"%snap_name)
    snapshot = SnapShotOps(snap_name,volobj=vol_list[0],create=True)
    assert(snapshot != None)
        # Write on remaning space of the volumes 
    logger.info("Starting write on other space of the vol ")
    kwargs = {'offset':"45g",'size':'5g',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.rand_read_write(vol_list, host, kwargs)
    assert (status==0)
        # disconnect the vol 
    logger.info("disconnecting the vol from the host")
    status = [host.disconnect_volume(v) for v in vol_list]
    assert(status != 0)
    time.sleep(5)
        #assert(status==0) 
        # restore using latest snapshot 
    logger.info("Running vol_restore using following snaphost : %s"%snap_name)
    snap_id = snapshot.snap_id
    status = pvlLibHandle.system.generic_api('POST', '/storage/snapshots/%s/restore'%snap_id) 
    assert(status != 200)
    time.sleep(60)
        # cheking data integrity by rading the volumes data 
        # connecting the vol 
    logger.info("connecting the vol")
    status = [host.connect_volume(v) for v in vol_list]
    assert(status != 0)
    time.sleep(5)
    logger.info("Reading from the raw device")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_read(vol_list, host, kwargs)
    assert (status==0)
    print("3. Vol restore after 5% IO on the vol:PASS")

################################ 4. Vol restore for degraded volumes 
        # Power off one drive 
    mediaList = media_group.get_media_group_disk()
    media = [mediaList[0]]
    logger.info("Powering off drive : %s"%media)
    status = power_off_drive(media,pvlLibHandle)
    time.sleep(30)
        # overwrite on the volume 
    logger.info("Starting overwrite on the vol-seq_write")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write(vol_list, host, kwargs)
    assert (status==0)
        # disconenct the vol 
    logger.info("disconnecting the vol from the host")
    status = [host.disconnect_volume(v) for v in vol_list]
    assert(status!=0)
    time.sleep(5)
        # restore the volumes using s2 
    logger.info("Running vol_restore using following snaphost : %s"%snap_name)
    status = pvlLibHandle.system.generic_api('POST', '/storage/snapshots/%s/restore'%snap_id)
    assert(status != 200)
    time.sleep(60)
        # connect the vol & verify the data 
    logger.info("connecting the vol")
    status = [host.connect_volume(v) for v in vol_list]
    assert(status!=0)
    time.sleep(5)
    logger.info("Reading from the raw device")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_read(vol_list, host, kwargs)
    print("4. Vol restore for degraded volumes:PASS")

################################ 5. Vol restore for critical voluems 
        # poweroff one more drive 
    media = [mediaList[1]]
    logger.info("Powering off drive : %s"%media)
    status = power_off_drive(media,pvlLibHandle)
    time.sleep(30)
        # overwrite on the volume
    logger.info("Starting overwrite on the vol-seq_write")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write(vol_list, host, kwargs)
    assert (status==0)
        # disconenct the vol
    logger.info("disconnecting the vol from the host")
    status = [host.disconnect_volume(v) for v in vol_list]
    assert(status!=0)
    time.sleep(5)
        # restore the volumes using s2
    logger.info("Running vol_restore using following snaphost : %s"%snap_name)
    status = pvlLibHandle.system.generic_api('POST', '/storage/snapshots/%s/restore'%snap_id)
    assert(status != 200)
    time.sleep(60)
        # connect the vol & verify the data
    logger.info("connecting the vol")
    status = [host.connect_volume(v) for v in vol_list]
    assert(status!=0)
    time.sleep(5)
    logger.info("Reading from the raw device")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_read(vol_list, host, kwargs)
    print("5. Vol restore for critical voluems:PASS")
        
################################ 6. Vol restore with rebuild (2>1)
        # Poweron one drive and start the rebuild
    media = [mediaList[0]]
    logger.info("Powering ON drive : %s"%media)
    status = power_on_drive(media,pvlLibHandle)
    time.sleep(120)
    logger.info("Start rebuild 2>1")
    status=media_group.rebuild_media_group() 
        # overwrite on the volume
    logger.info("Starting overwrite on the vol-seq_write")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write(vol_list, host, kwargs)
    assert (status==0)
        # disconenct the vol
    logger.info("disconnecting the vol from the host")
    status = [host.disconnect_volume(v) for v in vol_list]
    assert(status != None)
    time.sleep(5)
        # restore the volumes using s2
    logger.info("Running vol_restore using following snaphost : %s"%snap_name)
    status = pvlLibHandle.system.generic_api('POST', '/storage/snapshots/%s/restore'%snap_id)
    assert(status != 200)
    time.sleep(60)
        # connect the vol & verify the data
    logger.info("connecting the vol")
    status = [host.connect_volume(v) for v in vol_list]
    assert(status!=0)
    time.sleep(5)
    logger.info("Reading from the raw device")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_read(vol_list, host, kwargs)
    print("6. Vol restore with rebuild (2>1):PASS")
    
################################ 7. Vol restore with rebuild (1>0)
    media = [mediaList[1]]
    logger.info("Powering ON drive : %s"%media)
    status = power_on_drive(media,pvlLibHandle)
    time.sleep(120)
    logger.info("Start rebuild 1>0")
    status=media_group.rebuild_media_group()
        # overwrite on the volume
    logger.info("Starting overwrite on the vol-seq_write")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write(vol_list, host, kwargs)
    assert (status==0)
        # disconenct the vol
    logger.info("disconnecting the vol from the host")
    status = [host.disconnect_volume(v) for v in vol_list]
    assert(status!=0)
    time.sleep(5)
        # restore the volumes using s2
    logger.info("Running vol_restore using following snaphost : %s"%snap_name)
    status = pvlLibHandle.system.generic_api('POST', '/storage/snapshots/%s/restore'%snap_id)
    assert(status != 200)
    time.sleep(60)
        # connect the vol & verify the data
    logger.info("connecting the vol")
    status = [host.connect_volume(v) for v in vol_list]
    assert(status!=0)
    time.sleep(5)
    logger.info("Reading from the raw device")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_read(vol_list, host, kwargs)
    print("7. Vol restore with rebuild (1>0):PASS")

################################ 8. Vol restore with rebuild (2>0)
    media = [mediaList[0],mediaList[1]]
    logger.info("Powering OFF drive : %s"%media)
    status = power_off_drive(media,pvlLibHandle)
    time.sleep(120)
    logger.info("Powering ON drive : %s"%media)
    status = power_on_drive(media,pvlLibHandle)
    time.sleep(120)
        # start rebuild 
    logger.info("Start rebuild 2>0")
    status=media_group.rebuild_media_group()
        # overwrite on the volume
    logger.info("Starting overwrite on the vol-seq_write")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write(vol_list, host, kwargs)
    assert (status==0)
        # disconenct the vol
    logger.info("disconnecting the vol from the host")
    status = [host.disconnect_volume(v) for v in vol_list]
    assert(status!=0)
    time.sleep(5)
        # restore the volumes using s2
    logger.info("Running vol_restore using following snaphost : %s"%snap_name)
    status = pvlLibHandle.system.generic_api('POST', '/storage/snapshots/%s/restore'%snap_id)
    assert(status != 200)
    time.sleep(60)
        # connect the vol & verify the data
    logger.info("connecting the vol")
    status = [host.connect_volume(v) for v in vol_list]
    assert(status!=0)
    time.sleep(5)
    logger.info("Reading from the raw device")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_read(vol_list, host, kwargs)
    print("8. Vol restore with rebuild (2>0):PASS") 

################################ 9. Vol restore with clone is connected to the host
        # overwrite on the volume
    logger.info("Starting overwrite on the vol-seq_write")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write(vol_list, host, kwargs)
    assert (status==0)
        # create clone
    clone_name = str(snap_name)+str("_c1")
    cloneObj = CloneOps(clone_name,snapshot,create=True)
        # assign clone 
    assign = cloneobj.assign_clone(ports,hostnqn=[])
        # connect clone to the host 
    status = host.connect_volume(cloneObj)
    assert(status!=0)
    time.sleep(5)
        # start IO on the clone 
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write(cloneObj, host, kwargs)
    assert (status==0)
        # disconenct the vol
    logger.info("disconnecting the vol from the host")
    status = [host.disconnect_volume(v) for v in vol_list]
    assert(status!=0)
    time.sleep(5)
        # restore the volumes using s2
    logger.info("Running vol_restore using following snaphost : %s"%snap_name)
    status = pvlLibHandle.system.generic_api('POST', '/storage/snapshots/%s/restore'%snap_id)
    assert(status != 200)
    time.sleep(60) 
        # connect the vol & verify the data
    logger.info("connecting the vol")
    status = [host.connect_volume(v) for v in vol_list]
    assert(status!=0)
    time.sleep(5)
    logger.info("Reading from the raw device")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_read(vol_list, host, kwargs)
    print("9. Vol restore with clone is connected to the host:PASS")
    

    

################################ delete s2 and its child snapshot

pds_vol_restore_sanity()

