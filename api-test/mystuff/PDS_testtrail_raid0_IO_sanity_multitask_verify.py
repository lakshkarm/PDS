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

MEDIA_GROUP_CREATING = 0
MEDIA_GROUP_DELETING = 1
MEDIA_GROUP_ACTIVE = 2
MEDIA_GROUP_FAILED = 3
MEDIA_GROUP_DELETED = 4
MEDIA_GROUP_DISABLED = 5
MEDIA_GROUP_DEGRADED = 6
MEDIA_GROUP_CRITICAL = 7

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
        assert(drv_cnt > 8)

        # creating mediaGroup
    logger.info("Creating a MediaGroup")
    media_group = MediaGroupOps(pvlLibHandle, name, ZONE, md_type,create=True)
    assert(media_group != None)

        # creaing volumes
    vol_list =  []
    for i in range(VOL_CNT):
        volname = "%s_%s"%(VOL_PREFIX,i)
        logger.info("Creating voluems")
        vol=VolumeOps(md=media_group,name=volname,size=VOL_SIZE,vol_res=VOL_RES,flavor=FLAVOR,create=True)
        vol_list.append(vol)
        assert(vol != None)
    return media_group,vol_list


def IO_sanity_func(volType="online",funcname="pds_online_vol_IO_sanity"):
    log = PvltLogger(funcname,'INFO')
    logger = log.logger
    host = HostOps(HOST[0])
    fio = FioUtils()
    pvlLibHandle = pvlclient.New("2.0",CHASSIS_IP,logger=logger)
    result = pvlLibHandle.auth.login(user=CHASSIS_USER,password=CHASSIS_PASS)
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

    def io_patterns():
        io_pattern = ['0x5aef', '0xa1e', '0xb1', '0xfda789', '0xfefee','0xaaaa','0xffff','0xaee4','0xbebe1234','0xfff1aaa1']
        bs = ["4k","8k","16k","32k","64k","128k","256k","512k","1M","2M"]
        #io_type = ["seq_write:seq_read","rand_write:rand_read",]
        ## IO operations along with dif pattern 

        for pattern,block_size in zip(io_pattern,bs):
            logger.info("Starting IO  on all the volumes")
            kwargs = {'offset':"20k",'size':'70%',"verify_pattern":pattern,"verify_interval":4096,"do_verify":1,
                      "bs":block_size}
            logger.info("Starting Seq_write")
            # start write 
            status,response=fio.seq_write(vol_list, host, kwargs)
            assert (status == 0)
        
            logger.info("Starting Seq_read")
            # start read with the same pattern 
            status,response=fio.seq_read(vol_list, host, kwargs) 
            assert (status == 0)
   
            logger.info("Starting rand_write") 
            # start rand_write & read
            status,response=fio.rand_write(vol_list, host, kwargs)
            assert (status == 0)

            logger.info("Starting rand_read")
            status,response=fio.rand_read(vol_list, host, kwargs)
            assert (status == 0)
        
            logger.info("Starting Seq_read_write")
            # seq_read_write
            status,response=fio.seq_read_write(vol_list, host, kwargs)
            assert (status == 0)
    
            logger.info("Starting rand_read_write")
            # rand_read_write
            status,response=fio.rand_read_write(vol_list, host, kwargs)
            assert (status == 0)


        # starting multijob FIO load but without verification 
        logger.info("Starting multithreaded  write without verification  on the vol-seq_write")
        kwargs = {'offset':"0",'size':'80%',"numjobs":"8","bsrange":"4k-2M"}
        status,response=fio.seq_write(vol_list, host, kwargs)
        assert (status == 0)
    
        # Starting mutithreaded write with verification 
        logger.info("Starting  mutithreaded-write with verification on the vol-seq_write")
        kwargs = {'offset':"0",'size':'100%',"verify_pattern":"0xFFFF","verify_interval":4096,"do_verify":1,"numjobs":"1",
                  "bssplit":"4k/15:16k/15:32k/15:64k/15:128k/15:256k/10:512k/5:1m/5:2m/5","multithread_verification":"1"}
        status,response=fio.seq_write(vol_list, host, kwargs)
        assert (status == 0)

    if volType == "online":
         io_patterns()
         #assert(media_group.get_media_group_state() == 2)
         #for vol in vol_list:
             #state = vol.get_vol_state()
             #assert('Online' in state)

    if volType == "degraded":
        # Power off one drive
        media = media_group.md_disk[0]
        logger.info("Powering off drive : %s"%media)
        status = power_off_drive(media,pvlLibHandle)
        time.sleep(5)
         #assert(media_group.get_media_group_state() == 6)
         #for vol in vol_list:
             #state = vol.get_vol_state()
             #assert('Online, degraded' in state)

        # starting io 
        io_patterns()

        # poweron the drive again
        logger.info("Powering ON drive : %s"%media)
        status = power_on_drive(media,pvlLibHandle)
        time.sleep(60)

    if volType == "critical":
        # poweroff 2  drive
        media = [media_group.md_disk[0]] + [media_group.md_disk[1]]
        logger.info("Powering off drive : %s"%media)
        status = power_off_drive(media,pvlLibHandle)
        time.sleep(5)

         #assert(media_group.get_media_group_state() == 7)
         #for vol in vol_list:
             #state = vol.get_vol_state()
            #assert('Online, critical' in state)

        # starting io
        io_patterns()

        # Poweron one drive 
        media = [media_group.md_disk[0]]
        logger.info("Powering ON drive : %s"%media)
        status = power_on_drive(media,pvlLibHandle)
        time.sleep(60)
        media = [media_group.md_disk[1]]
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

