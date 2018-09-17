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

def base_function(pvlLibHandle,logger):
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
        sys.exit()
    if VOL_CNT > 1 :
        logger.error('Update the configuration As this test is currently written for 1 vol only')
        sys.exit()

        # creating mediaGroup
    logger.info("Creating a MediaGroup")
    media_group = MediaGroupOps(pvlLibHandle, name, ZONE, md_type,create=True)
    assert(media_group != None)

        # creaing volumes
    logger.info("Creating voluems")
    vol=VolumeOps(md=media_group,name=volname,size=VOL_SIZE,vol_res=VOL_RES,flavor=FLAVOR,create=True)
    assert(vol != None)
    return media_group,vol

################################ 1 Vol restore for unassigned volume
#def pds_vol_rollback_sanity():
@with_setup(setup=None, teardown=clear_zone_config)
@attr('raid0','sanity')
def pds_rollback_unassign_vol():
        #objects initialization & Authentication 
    log = PvltLogger(inspect.stack()[0][3],'INFO')
    logger = log.logger
    host = HostOps(HOST[0])
    fio = FioUtils()
    pvlLibHandle = pvlclient.New("2.0",CHASSIS_IP,logger=logger)
    result = pvlLibHandle.auth.login(user=CHASSIS_USER,password=CHASSIS_PASS)

         #calling base function to populate the objects 
    media_group,vol = base_function(pvlLibHandle,logger)

         #Creating a snapshot
    logger.info("Creating a snapshot : %s"%SNAP_PREFIX)
    snapshot = SnapShotOps(SNAP_PREFIX,volobj=vol,create=True)
    assert(snapshot != None)

        # Restore the vol using its snapshot
    status = vol.vol_rollback(snapshot,backup="true")
    assert(status == True)

        # delete forensic snapshot 
    status = snapshot.delete_all_forensic_snap()
    assert(status == True)
    logger.info("1 Vol restore for unassigned volume: PASS")

################################ 2 Vol restore after assign volume
@with_setup(setup=None, teardown=clear_zone_config)
@attr('raid0','sanity')
def pds_rollback_assign_vol():
        #objects initialization & Authentication
    log = PvltLogger(inspect.stack()[0][3],'INFO')
    logger = log.logger
    host = HostOps(HOST[0])
    fio = FioUtils()
    pvlLibHandle = pvlclient.New("2.0",CHASSIS_IP,logger=logger)
    result = pvlLibHandle.auth.login(user=CHASSIS_USER,password=CHASSIS_PASS)

        #calling base function to populate the objects
    media_group,vol = base_function(pvlLibHandle,logger)

        #Creating a snapshot
    logger.info("Creating a snapshot : %s"%SNAP_PREFIX)
    snapshot = SnapShotOps(SNAP_PREFIX,volobj=vol,create=True)
    assert(snapshot != None)
        # assigning vol 
    ports= get_volume_network_map(pvlLibHandle, ZONE)
    logger.info("Assigning vols ")
    status  = vol.assign_volume(ports,hostnqn=[])
    assert(status == True)

        # run vol rollback 
    try:
        status = vol.vol_rollback(snapshot,backup="true")
        #assert(vol.vol_rollback(snapshot,backup="true") == False)
        if(status == False):
            raise Exception
    except Exception:
        logger.info("Rollback operations can`t be perfomed on Assigned vol, Please-Unassign the vol and try again ")

################################## 3. Vol restore after 40% IO on the vol
@with_setup(setup=None, teardown=clear_zone_config)
@attr('raid0','sanity')
def pds_rollback_with_IO():
        #objects initialization & Authentication
    log = PvltLogger(inspect.stack()[0][3],'INFO')
    logger = log.logger
    host = HostOps(HOST[0])
    fio = FioUtils()
    pvlLibHandle = pvlclient.New("2.0",CHASSIS_IP,logger=logger)
    result = pvlLibHandle.auth.login(user=CHASSIS_USER,password=CHASSIS_PASS)

        #calling base function to populate the objects
    media_group,vol = base_function(pvlLibHandle,logger)

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
    kwargs = {'offset':"0",'size':'40%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write([vol], host, kwargs)
    assert (status == 0)

       #Taking snaphost 
    logger.info("Taking snapshot :%s"%SNAP_PREFIX)
    snapshot = SnapShotOps(SNAP_PREFIX,volobj=vol,create=True)
    assert(snapshot != None)

       #Write on remaning space of the volumes 
    logger.info("Starting write on other space of the vol ")
    kwargs = {'offset':"45g",'size':'5g',"verify_pattern":"0xffff","verify_interval":4096,"do_verify":1}
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
    kwargs = {'offset':"0",'size':'40%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_read([vol], host, kwargs)
    assert (status==0)

       #delete forensic snapshot
    status = snapshot.delete_all_forensic_snap()
    assert(status == True)

       # disconnect the vol to run teardown
    logger.info("disconnecting the vol from the host")
    status = host.disconnect_volume(vol)
    time.sleep(10)

################################ 4. Vol restore with clone is connected to the host
#@with_setup(setup=None, teardown=clear_zone_config)
@attr('raid0','sanity')
def pds_rollback_with_clone():
           #objects initialization & Authentication
    log = PvltLogger(inspect.stack()[0][3],'INFO')
    logger = log.logger
    host = HostOps(HOST[0])
    fio = FioUtils()
    pvlLibHandle = pvlclient.New("2.0",CHASSIS_IP,logger=logger)
    result = pvlLibHandle.auth.login(user=CHASSIS_USER,password=CHASSIS_PASS)

        #calling base function to populate the objects
    media_group,vol = base_function(pvlLibHandle,logger)

        # assigning vol 
    ports= get_volume_network_map(pvlLibHandle, ZONE)
    logger.info("Assigning vols ")
    status  = vol.assign_volume(ports,hostnqn=[])
    assert(status == True) 

            # connect vol
    logger.info("connecting vol to the host")
    status = host.connect_volume(vol)
    assert(status == 0)


        # write on the volume
    logger.info("Starting overwrite on the vol-seq_write")
    kwargs = {'offset':"0",'size':'40%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write([vol], host, kwargs)
    assert (status==0)

        # Creating a snapshot
    logger.info("Creating a snapshot : %s"%SNAP_PREFIX)
    snapshot = SnapShotOps(SNAP_PREFIX,volobj=vol,create=True)
    assert(snapshot != None)

        # create clone
    clone_name = str(SNAP_PREFIX)+str("_c1")
    logger.info("Creating clone name : %s"%clone_name)
    cloneObj = CloneOps(clone_name,snapshot,create=True)

        # assign clone 
    logger.info("Assigning clone %s to contollers"%cloneObj.name)
    assign = cloneObj.assign_clone(ports,hostnqn=[])

        # connect clone to the host 
    logger.info("Connecting clone %s to the host"%cloneObj.name)
    status = host.connect_volume(cloneObj)
    assert(status==0)

        # start IO on the clone 
    logger.info("Staring write IO to the clone %s"%clone_name)
    kwargs = {'offset':"0",'size':'40%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write([cloneObj], host, kwargs)
    assert (status==0)

       # overwrite on the volume
    logger.info("Starting overwrite on the vol-seq_write")
    kwargs = {'offset':"0",'size':'40%',"verify_pattern":"0xffff","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write([vol], host, kwargs)
    assert (status==0)

        # disconenct the vol
    logger.info("disconnecting the vol from the host")
    status = host.disconnect_volume(vol)
    time.sleep(10)

        # unassign  the vol
    status = vol.unassign_volume()
    assert(status == True)

        # restore the volumes using s2
    status = vol.vol_rollback(snapshot,backup="true")
    assert(status == True)

        # assigning the vol back 
    logger.info("Assigning vols ")
    status  = vol.assign_volume(ports,hostnqn=[])
    assert(status == True)
        # connect the vol 
    logger.info("connecting the vol")
    status = host.connect_volume(vol)
    assert(status == 0)
        # reding the data
    logger.info("Reading from the raw device")
    kwargs = {'offset':"0",'size':'40%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_read([vol], host, kwargs)
    assert(status == 0)

        # delete forensic snapshot
    status = snapshot.delete_all_forensic_snap()
    assert(status == True)

        # disconnect the vol to run teardown
    logger.info("disconnecting the vol from the host")
    status = host.disconnect_volume(vol)
    time.sleep(10)

        # disconnet the clone
    logger.info("disconnecting clone  : %s"%cloneObj.name)
    status = host.disconnect_volume(cloneObj)
    time.sleep(10)
