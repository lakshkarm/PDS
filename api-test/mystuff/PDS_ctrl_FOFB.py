#!/usr/bin/python -B
import random,sys
import inspect
import logging
import json
import pvlclient
import time
import requests
from os import environ
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from nose.plugins.attrib import attr
from nose.tools import with_setup
import multiprocessing,time


from lib.misc.PVLLogger import PvltLogger
from lib.storage.MEDIAGROUP import MediaGroupOps
from lib.storage.VOLUME import VolumeOps
from lib.storage.SNAPSHOT import SnapShotOps
from lib.storage.CLONE import CloneOps
from lib.ioutils.HOSTUTILS import HostOps
from lib.ioutils.FIOUTILS import FioUtils
from lib.storage.CLEARCONFIG import clear_config
from lib.system.DRIVEUTILS import * 

from lib.system.CONTROLLER import (
    get_volume_network_map,
    get_all_ids_in_zone,
    ControllerOps
)

from lib.system.DRIVEUTILS import (
    get_active_drive_count
    )
from lib.storage.CLEARCONFIG import(
    clear_zone_config
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
    VOL_CNT,
    FLAVOR,
    VOL_PREFIX,
    VOL_RES,
    FILE_SYSTEM,
    SNAP_PREFIX,

)

from lib.system.CONTROLLER import (
    get_volume_network_map
)

def base_function(pvlLibHandle,logger):
        # defining variables
    name = MEDIA_GROUP_NAME
    md_type = MEDIA_GROUP_TYPE
        # validation for prerequisits
    drv_cnt = get_active_drive_count(ZONE,pvlLibHandle)
    logger.info(ZONE)
    logger.info(drv_cnt)

    if drv_cnt < 9 :
        logger.error('Not sufficient drives active drive count=%s'%drv_cnt)
        sys.exit()

        # creating mediaGroup
    logger.info("Creating a MediaGroup")
    media_group = MediaGroupOps(pvlLibHandle, name, ZONE, md_type,create=True)
    assert(media_group != None)

        # creaing volumes
    vol_list =  []
    for i in range(VOL_CNT):
        volname = str(VOL_PREFIX) + str("_%s"%i)
        logger.info("Creating voluems")
        vol=VolumeOps(md=media_group,name=volname,size=VOL_SIZE,vol_res=VOL_RES,flavor=FLAVOR,create=True)
        vol_list.append(vol)
        assert(vol != None)
    return media_group,vol_list

################################ 1 FOFB on online vol (graceful)
@with_setup(setup=None, teardown=clear_zone_config)
@attr('raid6','sanity')
def pds_ctrl_fofb():
        #objects initialization & Authentication 
    log = PvltLogger(inspect.stack()[0][3],'INFO')
    logger = log.logger
    host = HostOps(HOST[0])
    fio = FioUtils()
    pvlLibHandle = pvlclient.New("2.0",CHASSIS_IP,logger=logger)
    result = pvlLibHandle.auth.login(user=CHASSIS_USER,password=CHASSIS_PASS)
    ctrl_id = list(get_all_ids_in_zone(ZONE))
    ctrl_obj_0 = ControllerOps(pvlLibHandle,ctrl_id[0],"rdma")
    ctrl_obj_1 = ControllerOps(pvlLibHandle,ctrl_id[1],"rdma")


        #calling base function to populate the objects 
    media_group,vol_list = base_function(pvlLibHandle,logger)

        # assigning vol
    ports = get_volume_network_map(pvlLibHandle, ZONE)
    logger.info("Assigning vols ")
    for vol in vol_list:
        status  = vol.assign_volume(ports,hostnqn=[])
        assert(status == True)

        # connet to the host
        status = host.connect_volume(vol)
        assert(status == 0)
    
    def startIO():
        p1 = multiprocessing.current_process()
        logger.info("Starting : %s : %s"%(p1.name,p1.pid))
        print "Starting :",p1.name,p1.pid
        logger.info("Starting write on the vol-seq_write")
        kwargs = {'offset':"0",'size':'100%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
        status,response=fio.seq_write(vol_list, host, kwargs)
        assert (status == 0)

        
        #start fio on all the volumes
    p1 = multiprocessing.Process(name="StartFio",target=startIO)
    p1.start()
     #logger.info("Starting write on the vol-seq_write")
     #kwargs = {'offset':"0",'size':'1%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
     #status,response=fio.seq_write(vol_list, host, kwargs)
     #assert (status == 0) 
    # start FOFB with fresh write
    logger.info("Start controler poweroff/on")
    for i in range(10):
        # controller poeroff
        status = ctrl_obj_0.power_off()
        #assert(status == True)
        time.sleep(60)

        # controller poweron
        status = ctrl_obj_0.power_on()
        #assert(status == True)
        time.sleep(150)
        
        # poweroff/on another controller
        status = ctrl_obj_1.power_off()
        #assert(status == True)
        time.sleep(60)
        
        # poweroff/on another controller
        status = ctrl_obj_1.power_on()
        #assert(status == True)
        time.sleep(60)

    p1.join()
        
    #disconnect the vol
    for vol in vol_list:
        logger.info("disconnecting the vol from the host")
        status = host.disconnect_volume(vol)
        time.sleep(10)
'''
################################ 2. Graceful(controller power off/on ) FOFB on degraded vol 

@with_setup(setup=None, teardown=clear_zone_config)
@attr('raid6','sanity')
def pds_degraded_vol__fofb():
        #objects initialization & Authentication 
    log = PvltLogger(inspect.stack()[0][3],'INFO')
    logger = log.logger
    host = HostOps(HOST[0])
    fio = FioUtils()
    pvlLibHandle = pvlclient.New("2.0",CHASSIS_IP,logger=logger)
    result = pvlLibHandle.auth.login(user=CHASSIS_USER,password=CHASSIS_PASS)
    ctrl_id = list(get_all_ids_in_zone(ZONE)) 
    ctrl_obj_0 = ControllerOps(pvlLibHandle,ctrl_id[0],"rdma")
    ctrl_obj_1 = ControllerOps(pvlLibHandle,ctrl_id[1],"rdma")
    
        #calling base function to populate the objects 
    media_group,vol_list = base_function(pvlLibHandle,logger)

        # assigning vol
    ports = get_volume_network_map(pvlLibHandle, ZONE)
    logger.info("Assigning vols ")
    for vol in vol_list:
        status  = vol.assign_volume(ports,hostnqn=[])
        assert(status == True)

        # connet to the host
        status = host.connect_volume(vol)
        assert(status == 0)

    # power off one drive 
    mediaList = media_group.get_media_group_disk()
    media = [mediaList[0]]
    logger.info("Powering off drive : %s"%media)
    status = power_off_drive(media,pvlLibHandle)

    # start IO on all the vols 
    logger.info("Starting write on the vol-seq_write")
    kwargs = {'offset':"0",'size':'1%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write(vol_list, host, kwargs)
    assert (status == 0)

    # start FOFB with fresh write 
    logger.info("Start controler poweroff/on")
    for i in range(1):
        # controller poeroff 
        status = ctrl_obj_0.power_off()
        #assert(status == True)
        time.sleep(60)
        
        # controller poweron 
        status = ctrl_obj_0.power_on()        
        #assert(status == True)
        time.sleep(60)

    # start overwrite on the vols 
    logger.info("Starting write on the vol-seq_write")
    kwargs = {'offset':"0",'size':'1%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write(vol_list, host, kwargs)
    assert (status == 0)

    # start FOFB with over-write 
    for i in range(1):
        # controller poeroff 
        status = power_off()
        assert(status == True)
        time.sleep(60)
        
        # controller poweron 
        status = power_on()        
        assert(status == True)
        time.sleep(60)
    
    # powerOn the drive 
    logger.info("Powering ON drive : %s"%media)
    status = power_on_drive(media,pvlLibHandle)
    time.sleep(60)

    #Rebuild the mg 
    logger.info("Start rebuild ")
    status=media_group.synchronous_rebuild_media_group()
 
    #disconnect the vol
    for vol in vol_list:
        logger.info("disconnecting the vol from the host")
        status = host.disconnect_volume(vol)
        time.sleep(10)
'''
