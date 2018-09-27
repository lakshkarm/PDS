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
    get_volume_network_map
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

def base_function(pvlLibHandle,logger,md_type):
        # defining variables
    name = MEDIA_GROUP_NAME
    md_type = MEDIA_GROUP_TYPE
    volname = VOL_PREFIX
        # validation for prerequisits
    drv_cnt = get_active_drive_count(ZONE,pvlLibHandle)
    logger.info(ZONE)
    logger.info(drv_cnt)

    if drv_cnt < 9 :
        logger.error('Not sufficient drives active drive count=%s'%drv_cnt)
        assert(drv_cnt > 8 )

        # creating mediaGroup
    logger.info("Creating a MediaGroup")
    media_group = MediaGroupOps(pvlLibHandle, name, ZONE, md_type,create=True)
    assert(media_group != None)

        # creaing volumes
    logger.info("Creating voluems")
    vol=VolumeOps(md=media_group,name=volname,size=VOL_SIZE,vol_res=VOL_RES,flavor=FLAVOR,create=True)
    assert(vol != None)
    return media_group,vol

################################## 1. Vol restore after 40% IO on the vol
@with_setup(setup=None, teardown=clear_zone_config)
@attr('raid0','Sanity')
def pds_raid0_vol_restore_IO():
        #objects initialization & Authentication
    log = PvltLogger(inspect.stack()[0][3],'INFO')
    logger = log.logger
    host = HostOps(HOST[0])
    fio = FioUtils()
    pvlLibHandle = pvlclient.New("2.0",CHASSIS_IP,logger=logger)
    result = pvlLibHandle.auth.login(user=CHASSIS_USER,password=CHASSIS_PASS)

        #calling base function to populate the objects
    media_group,vol = base_function(pvlLibHandle,logger,'RAID-0 (9+0)')

        # assign the vol 
    ports= get_volume_network_map(pvlLibHandle, ZONE)
    logger.info("Assigning vols ")
    status  = vol.assign_volume(ports,hostnqn=[])
    assert(status == True)

        # connet to the host 
    status = host.connect_volume(vol)
    assert(status == 0)

       #start fio on all the volumes 
    logger.info("Starting write on the vol-seq_write")
    kwargs = {'offset':"0","bs":"64k",'size':'40%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write([vol], host, kwargs)
    assert (status == 0)

       #Taking snaphost 
    logger.info("Taking snapshot :%s"%SNAP_PREFIX)
    snapshot = SnapShotOps(SNAP_PREFIX,volobj=vol,create=True)
    assert(snapshot != None)

       #Write on remaning space of the volumes 
    logger.info("Starting write on other space of the vol ")
    kwargs = {'offset':"45g","bs":"64k",'size':'5g',"verify_pattern":"0xffff","verify_interval":4096,"do_verify":1}
    status,response=fio.rand_write([vol], host, kwargs)
    assert (status == 0)

       #disconnect the vol 
    logger.info("disconnecting the vol from the host")
    status = host.disconnect_volume(vol)
    time.sleep(10)

       # unassign  the vol 
    status = vol.unassign_volume()
    assert(status == True)

       #restore using latest snapshot 
    status = vol.vol_rollback(snapshot,backup="true")
    assert(status == True)

       #cheking data integrity by rading the volumes data 
       #assign and then connecting the vol 
    logger.info("Assigning vols ")
    status  = vol.assign_volume(ports,hostnqn=[])
    assert(status == True)

    logger.info("connecting the vol")
    status = host.connect_volume(vol)
    assert(status == 0)

    logger.info("Reading from the raw device")
    kwargs = {'offset':"0","bs":"64k",'size':'40%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_read([vol], host, kwargs)
    assert (status==0)

       #delete forensic snapshot
    status = snapshot.delete_all_forensic_snap()
    assert(status == True)
    
       # delete parent snapshot
    logger.info("deleting parent snapshot")
    status = snapshot.delete_snapshot()
    assert(status == True)

       # disconnect the vol to run teardown
    logger.info("disconnecting the vol from the host")
    status = host.disconnect_volume(vol)
    time.sleep(10)
    assert(vol.unassign_volume())
    assert(vol.delete_volume())
    assert(media_group.delete_mediagroup())


