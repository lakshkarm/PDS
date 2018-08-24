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
    VOL_CNT,
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


def pds_raid6_io_sanity():
    host = HostOps(HOST[0])
    fio = FioUtils()
        # give function name as log file name
    log = PvltLogger("raid6_io_sanity",'INFO')
    logger = log.logger
    name = MEDIA_GROUP_NAME
    pvlLibHandle = pvlclient.New("2.0",CHASSIS_IP,logger=logger)
    result = pvlLibHandle.auth.login(user=CHASSIS_USER,password=CHASSIS_PASS)
        ## velidation for prerequisits 
    drv_cnt = get_active_drive_count(ZONE,pvlLibHandle)
    logger.info(ZONE)
    logger.info(drv_cnt)
    if drv_cnt < 9 :
        logger.error('Not sufficient drives active drive count=%s'%drv_cnt)
        sys.exit()
    if VOL_CNT > 1 :
        logger.error('Update the configuration As this test is currently written for 1 vol only')
        sys.exit()
    md_type = MEDIA_GROUP_TYPE
        ## creating mediaGroup
    logger.info("Creating a MediaGroup")
    media_group = MediaGroupOps(pvlLibHandle, name, ZONE, md_type,create=True)
    assert(media_group != None )
        ## creaing volumes 
    logger.info("Creating voluems")
    #vol_list = []
    volname = VOL_PREFIX
    vol=VolumeOps(md=media_group,name=volname,size=VOL_SIZE,vol_res=VOL_RES,flavor=FLAVOR,create=True)
    assert(vol != None )
        # Assigning and connecting the volume
    ports = get_two_port_diff_ctlr(ZONE)
    logger.info("Assigning vols ")
    status  = vol.assign_volume(ports,hostnqn=[])
    assert(status)
    status = host.connect_volume(vol)
    time.sleep(10)
    assert(status == 0)

    #ioitems = ['write','randwrite','readwrite','randrw','read']
    #blk_list = ['4k','8k','16k','32k','64k','128k','256k','512k','1m','2m']
    ioitems = ['write']
    blk_list = ['4k']

################################ 1. FIO on online volume
        #start fio on all the volumes with BS:4k/IODEPTH:128
     for blk_size in blk_list:
         for io_type in ioitems:
             logger.info("Starting IO Online volumes : IO_TYPE=%s :BS=%s"%(io_type,blk_size))
             kwargs = {'offset':"0",'bs':blk_size,'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
             status,response=fio.generic_fio(io_type,[vol], host, kwargs)
             assert (status == 0)
             logger.info("Completed IO for Online volume with:IO_TYPE=%s||BS=%s"%(io_type,blk_size))
    
################################ 2. IO on degraded volumes 
        # Power off one drive 
    media = media_group.md_disk[0]
    #media = [mediaList[0]]
    logger.info("Powering off drive : %s"%media)
    status = power_off_drive([media],pvlLibHandle)
    time.sleep(30)
        # overwrite on the volume 
    for blk_size in blk_list:
        for io_type in ioitems:
            logger.info("Starting IO Online volumes : IO_TYPE=%s :BS=%s"%(io_type,blk_size))
            kwargs = {'offset':"0",'bs':blk_size,'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
            status,response=fio.generic_fio(io_type,[vol], host, kwargs)
            assert (status == 0)
            logger.info("Completed IO for degraded volume with:IO_TYPE=%s||BS=%s"%(io_type,blk_size))

################################ 3. IO on critical voluems 
        # poweroff one more drive 
    #media = [mediaList[1]]
    media = media_group.md_disk[1]
    logger.info("Powering off drive : %s"%media)
    status = power_off_drive([media],pvlLibHandle)
    time.sleep(30)
        # overwrite on the volume
    for blk_size in blk_list:
        for io_type in ioitems:
            logger.info("Starting IO Online volumes : IO_TYPE=%s :BS=%s"%(io_type,blk_size))
            kwargs = {'offset':"0",'bs':blk_size,'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
            status,response=fio.generic_fio(io_type,[vol], host, kwargs)
            assert (status == 0)
            logger.info("Completed IO for Critical volume with:IO_TYPE=%s||BS=%s"%(io_type,blk_size))

################################ 6. IO with rebuild (2>1)
        # Poweron one drive and start the rebuild
    #media = [mediaList[0]]
    media = media_group.md_disk[0]
    logger.info("Powering ON drive : %s"%media)
    status = power_on_drive([media],pvlLibHandle)
    time.sleep(120)
    logger.info("Start rebuild 2>1")
    status=media_group.rebuild_media_group() 
        # overwrite on the volume
    for blk_size in blk_list:
        for io_type in ioitems:
            logger.info("Starting IO Online volumes : IO_TYPE=%s :BS=%s"%(io_type,blk_size))
            kwargs = {'offset':"0",'bs':blk_size,'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
            status,response=fio.generic_fio(io_type,[vol], host, kwargs)
            assert (status == 0)
            logger.info("Completed IO for degarded volume after 2>1 rebuild  with:IO_TYPE=%s||BS=%s"%(io_type,blk_size))

################################ 7. IO with rebuild (1>0)
    #media = [mediaList[1]]
    #media = media_group.md_disk[1]
    media = media_group.md_disk[0]
    logger.info("Powering ON drive : %s"%media)
    status = power_on_drive([media],pvlLibHandle)
    time.sleep(120)
    logger.info("Start rebuild 1>0")
    status=media_group.rebuild_media_group()
        # overwrite on the volume
    for blk_size in blk_list:
        for io_type in ioitems:
            logger.info("Starting IO Online volumes : IO_TYPE=%s :BS=%s"%(io_type,blk_size))
            kwargs = {'offset':"0",'bs':blk_size,'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
            status,response=fio.generic_fio(io_type,[vol], host, kwargs)
            assert (status == 0)
            logger.info("Completed IO for online  volume after 1>0 rebuild  with:IO_TYPE=%s||BS=%s"%(io_type,blk_size))

################################ 8. IO with rebuild (2>0)
    media = [media_group.md_disk[1],media_group.md_disk[0]]
    logger.info("Powering OFF drive : %s"%media)
    status = power_off_drive([media_group.md_disk[1],media_group.md_disk[0]],pvlLibHandle)
    time.sleep(60)
    logger.info("Powering ON drive : %s"%media)
    status = power_on_drive([media_group.md_disk[1],media_group.md_disk[0]],pvlLibHandle)
    time.sleep(60)
        # start rebuild 
    logger.info("Start rebuild 2>0")
    status=media_group.rebuild_media_group()
        # overwrite on the volume
    for blk_size in blk_list:
        for io_type in ioitems:
            logger.info("Starting IO Online volumes : IO_TYPE=%s :BS=%s"%(io_type,blk_size))
            kwargs = {'offset':"0",'bs':blk_size,'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
            status,response=fio.generic_fio(io_type,[vol], host, kwargs)
            assert (status == 0)
            logger.info("Completed IO for online volume after 2>0 rebuild with:IO_TYPE=%s||BS=%s"%(io_type,blk_size))

################################ delete s2 and its child snapshot

pds_raid6_io_sanity()
