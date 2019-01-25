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
    ControllerOps, 
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


def IO_sanity_func(volType="online",funcname="pds_online_vol_IO_sanity"):
    #objects initialization & Authentication
    log = PvltLogger(funcname,'INFO')
    logger = log.logger
    host = HostOps(HOST[0])
    fio = FioUtils()
    pvlLibHandle = pvlclient.New("2.0",CHASSIS_IP,logger=logger)
    result = pvlLibHandle.auth.login(user=CHASSIS_USER,password=CHASSIS_PASS)

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

    if volType == "online":
        #star fresh write on all the volumes
        logger.info("Starting fresh write on the vol-seq_write")
        kwargs = {'offset':"0",'size':'30%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1,
                  "bs":"64k"}
        status,response=fio.seq_write(vol_list, host, kwargs)
        assert (status == 0)

        # starting overwrite with diff pattern
        logger.info("Starting overwrite on the vol-seq_write")
        kwargs = {'offset':"0",'size':'50%',"verify_pattern":"0xFFFF","verify_interval":4096,"do_verify":1,
                  "bs":"64k"}
        status,response=fio.seq_write(vol_list, host, kwargs)
        assert (status == 0)

        # starting multijob FIO load but without verification 
        logger.info("Starting multithreaded  write without verification  on the vol-seq_write")
        kwargs = {'offset':"0",'size':'70%',"numjobs":"8","bsrange":"4k-2M"}
        status,response=fio.seq_write(vol_list, host, kwargs)
        assert (status == 0)
    
        # Starting mutithreaded write with verification 
        logger.info("Starting  mutithreaded-write with verification on the vol-seq_write")
        kwargs = {'offset':"0",'size':'100%',"verify_pattern":"0xFFFF","verify_interval":4096,"do_verify":1,"numjobs":"1",
                  "bssplit":"4k/15:16k/15:32k/15:64k/15:128k/15:256k/10:512k/5:1m/5:2m/5","multithread_verification":"1"}
        status,response=fio.seq_write(vol_list, host, kwargs)
        assert (status == 0)

    if volType == "degraded":
        # Power off one drive
        mediaList = media_group.get_media_group_disk()
        media = [mediaList[0]]
        logger.info("Powering off drive : %s"%media)
        status = power_off_drive(media,pvlLibHandle)

        assert(media_group.get_media_group_state() == 6)

        #star fresh write on all the volumes
        logger.info("Starting fresh write on the vol-seq_write")
        kwargs = {'offset':"0",'size':'30%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1,
                  "bs":"64k"}
        status,response=fio.seq_write(vol_list, host, kwargs)
        assert (status == 0)

        # starting overwrite with diff pattern
        logger.info("Starting overwrite on the vol-seq_write")
        kwargs = {'offset':"0",'size':'50%',"verify_pattern":"0xFFFF","verify_interval":4096,"do_verify":1,
                  "bs":"64k"}
        status,response=fio.seq_write(vol_list, host, kwargs)
        assert (status == 0)

        # starting multijob FIO load but without verification
        logger.info("Starting multithreaded  write without verification  on the vol-seq_write")
        kwargs = {'offset':"0",'size':'70%',"numjobs":"8","bsrange":"4k-2M"}
        status,response=fio.seq_write(vol_list, host, kwargs)
        assert (status == 0)

        # Starting mutithreaded write with verification
        logger.info("Starting  mutithreaded-write with verification on the vol-seq_write")
        kwargs = {'offset':"0",'size':'100%',"verify_pattern":"0xFFFF","verify_interval":4096,"do_verify":1,"numjobs":"1",
                  "bssplit":"4k/15:16k/15:32k/15:64k/15:128k/15:256k/10:512k/5:1m/5:2m/5","multithread_verification":"1"}
        status,response=fio.seq_write(vol_list, host, kwargs)
        assert (status == 0)

        # poweron the drive again
        logger.info("Powering ON drive : %s"%media)
        status = power_on_drive(media,pvlLibHandle)
        time.sleep(60)

    if volType == "critical":
        # poweroff 2  drive
        mediaList = media_group.get_media_group_disk()
        media = [mediaList[0]] + [mediaList[1]]
        logger.info("Powering off drive : %s"%media)
        status = power_off_drive(media,pvlLibHandle)

        assert(media_group.get_media_group_state() == 7)

        #star fresh write on all the volumes
        logger.info("Starting fresh write on the vol-seq_write")
        kwargs = {'offset':"0",'size':'30%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1,
                  "bs":"64k"}
        status,response=fio.seq_write(vol_list, host, kwargs)
        assert (status == 0)

        # starting overwrite with diff pattern
        logger.info("Starting overwrite on the vol-seq_write")
        kwargs = {'offset':"0",'size':'50%',"verify_pattern":"0xFFFF","verify_interval":4096,"do_verify":1,
                  "bs":"64k"}
        status,response=fio.seq_write(vol_list, host, kwargs)
        assert (status == 0)

        # starting multijob FIO load but without verification
        logger.info("Starting multithreaded  write without verification  on the vol-seq_write")
        kwargs = {'offset':"0",'size':'70%',"numjobs":"8","bsrange":"4k-2M"}
        status,response=fio.seq_write(vol_list, host, kwargs)
        assert (status == 0)

        # Starting mutithreaded write with verification
        logger.info("Starting  mutithreaded-write with verification on the vol-seq_write")
        kwargs = {'offset':"0",'size':'100%',"verify_pattern":"0xFFFF","verify_interval":4096,"do_verify":1,"numjobs":"1",
                  "bssplit":"4k/15:16k/15:32k/15:64k/15:128k/15:256k/10:512k/5:1m/5:2m/5","multithread_verification":"1"}
        status,response=fio.seq_write(vol_list, host, kwargs)
        assert (status == 0)

        # Poweron one drive 
        media = [mediaList[0]]
        logger.info("Powering ON drive : %s"%media)
        status = power_on_drive(media,pvlLibHandle)
        time.sleep(60)
        media = [mediaList[1]]
        logger.info("Powering ON drive : %s"%media)
        status = power_on_drive(media,pvlLibHandle)
        time.sleep(60)

    
        
#1#.Online vol IO test
@with_setup(setup=None, teardown=clear_zone_config)
@attr('raid6','sanity')
def pds_online_vol_IO_sanity():
    try:
        IO_sanity_func(volType="online",funcname="pds_online_vol_IO_sanity")
        logger.info('********* PASSED *********')
    except Exception as E:
        logger.error('********* FAILED *********\n',exc_info=True)
        raise E

#2#.Degraded vol IO test
@with_setup(setup=None, teardown=clear_zone_config)
@attr('raid6','sanity')
def pds_degraded_vol_IO_sanity():
    try:
        IO_sanity_func(volType="degraded",funcname="pds_degraded_vol_IO_sanity")
        logger.info('********* PASSED *********')
    except Exception as E:
        logger.error('********* FAILED *********\n',exc_info=True)
        raise E

#3#.Critical vol IO test
@with_setup(setup=None, teardown=clear_zone_config)
@attr('raid6','sanity')
def pds_critical_vol_IO_sanity():
    try:
        IO_sanity_func(volType="critical",funcname="pds_critical_vol_IO_sanity")
        logger.info('********* PASSED *********')
    except Exception as E:
        logger.error('********* FAILED *********\n',exc_info=True)
        raise E

        
    

    
    
        
    

