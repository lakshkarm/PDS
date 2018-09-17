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
    get_single_ctlr_port,
    get_two_port_diff_ctlr,
    get_dual_port_ctlr
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

from lib.system.DRIVEUTILS import (
    get_active_drive_count,
    power_off_drive,
    power_on_drive
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

################################ 1 Vol restore for unassigned volume
#def pds_vol_rollback_sanity():
@with_setup(setup=None, teardown=clear_zone_config)
@attr('raid6','sanity')
def pds_io_sanity_with_snap_online_vol():
        #objects initialization & Authentication 
    log = PvltLogger(inspect.stack()[0][3],'INFO')
    logger = log.logger
    host = HostOps(HOST[0])
    fio = FioUtils()
    pvlLibHandle = pvlclient.New("2.0",CHASSIS_IP,logger=logger)
    result = pvlLibHandle.auth.login(user=CHASSIS_USER,password=CHASSIS_PASS)

        #calling base function to populate the objects 
    media_group,vol_list = base_function(pvlLibHandle,logger)

        # assigning vol
    ports = get_two_port_diff_ctlr(ZONE)
    logger.info("Assigning vols ")
    for vol in vol_list:
        status  = vol.assign_volume(ports,hostnqn=[])
        assert(status == True)

        # connet to the host
        status = host.connect_volume(vol)
        assert(status == 0)
        
    for i in range(5):
        snap_list = []
           #start fio on all the volumes
        logger.info("Starting write on the vol-seq_write")
        kwargs = {'offset':"0",'size':'50%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
        status,response=fio.seq_write(vol_list, host, kwargs)
        assert (status == 0) 

        for vol in vol_list:
               #Taking snaphost 
            snap_name = str(vol.name) + str("_%s"%SNAP_PREFIX)
            logger.info("Taking snapshot :%s"%snap_name)
            snapshot = SnapShotOps(snap_name,volobj=vol,create=True)
            assert(snapshot != None)
            snap_list.append(snapshot)
    
           #Write on remaning space of the volumes 
        logger.info("Starting write on other space of the vol ")
        kwargs = {'offset':"0",'size':'40%',"verify_pattern":"0xffff","verify_interval":4096,"do_verify":1}
        status,response=fio.rand_write(vol_list, host, kwargs)
        assert (status == 0)
        
        # delete snapshot 
        for snap in snap_list:
            status = snap.delete_snapshot()
            assert (status == True)
        time.sleep(300)
    
    #disconnect the vol
    for vol in vol_list:
        logger.info("disconnecting the vol from the host")
        status = host.disconnect_volume(vol)
        #assert(status == 0) 

