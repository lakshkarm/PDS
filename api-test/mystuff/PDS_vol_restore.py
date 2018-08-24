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
    FILE_SYSTEM

)

from lib.system.DRIVEUTILS import (
    get_active_drive_count,
    power_off_drive,
    power_on_drive
    )
# import some extra mofules 
import multiprocessing,time


#def pds_vol_rollback_sanity():
@with_setup(setup=None, teardown=clear_zone_config)
@attr('vol_rollback_sanity')
def pds_rollback_unassign_vol():
################################ 1 Vol restore for unassigned volume
        #objects initialization & Authentication 
    log = PvltLogger(inspect.stack()[0][3],'INFO')
    logger = log.logger
    host = HostOps(HOST[0])
    fio = FioUtils()
    pvlLibHandle = pvlclient.New("2.0",CHASSIS_IP,logger=logger)
    result = pvlLibHandle.auth.login(user=CHASSIS_USER,password=CHASSIS_PASS)
        # defining variables 
    name = MEDIA_GROUP_NAME
    md_type = MEDIA_GROUP_TYP
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
    time.sleep(10)
         #Creating a snapshot
    snap_name = "s1" 
    logger.info("Creating a snapshot : %s"%snap_name)
    snapshot = SnapShotOps(snap_name,volobj=vol,create=True)
    assert(snapshot != None)
    time.sleep(10)
        # Restore the vol using its snapshot
    status = vol.vol_rollback(snapshot,backup="true")
    assert(status == True)
    time.sleep(60)
        # delete forensic snapshot 
    status = snapshot.delete_all_forensic_snap()
    assert(status == True)
    print("1 Vol restore for unassigned volume: PASS")
'''
################################ 2 Vol restore after assign volume
@with_setup(setup=None, teardown=clear_zone_config)
@attr('vol_rollback_sanity')
def pds_rollback_assign_vol():
        #objects initialization & Authentication
    log = PvltLogger(inspect.stack()[0][3],'INFO')
    logger = log.logger
    host = HostOps(HOST[0])
    fio = FioUtils()
    pvlLibHandle = pvlclient.New("2.0",CHASSIS_IP,logger=logger)
    result = pvlLibHandle.auth.login(user=CHASSIS_USER,password=CHASSIS_PASS)
        # defining variables
    name = MEDIA_GROUP_NAME
    md_type = MEDIA_GROUP_TYP
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
    time.sleep(10)
         #Creating a snapshot
    snap_name = "s1"
    logger.info("Creating a snapshot : %s"%snap_name)
    snapshot = SnapShotOps(snap_name,volobj=vol,create=True)
    assert(snapshot != None)
    time.sleep(10)
    ports = get_two_port_diff_ctlr(ZONE)
    logger.info("Assigning vols ")
    status  = vol.assign_volume(ports,hostnqn=[])
    assert(status == True)
        # run vol rollback 
    status = vol.vol_rollback(snapshot,backup="true")
    assert(status == True)
    time.sleep(60)
        # delete forensic snapshot
    status = snapshot.delete_all_forensic_snap()
    assert(status == True)
    print("2 Vol restore after assign volume:PASS")
    
################################## 3. Vol restore after 5% IO on the vol
@with_setup(setup=None, teardown=clear_zone_config)
@attr('vol_rollback_sanity')
def pds_rollback_with_IO():
        #objects initialization & Authentication
    log = PvltLogger(inspect.stack()[0][3],'INFO')
    logger = log.logger
    host = HostOps(HOST[0])
    fio = FioUtils()
    pvlLibHandle = pvlclient.New("2.0",CHASSIS_IP,logger=logger)
    result = pvlLibHandle.auth.login(user=CHASSIS_USER,password=CHASSIS_PASS)
        # defining variables
    name = MEDIA_GROUP_NAME
    md_type = MEDIA_GROUP_TYP
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
    time.sleep(10)
        # assign the vol 
    ports = get_two_port_diff_ctlr(ZONE)
    logger.info("Assigning vols ")
    status  = vol.assign_volume(ports,hostnqn=[])
    assert(status == True)
        # connet to the host 
    status = host.connect_volume(vol)
    time.sleep(10)
    assert(status == 0)
       #start fio on all the volumes 
    logger.info("Starting write on the vol-seq_write")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write([vol], host, kwargs)
    assert (status == 0)
       #Taking snaphost 
    snap_name = "s2" 
    logger.info("Taking snapshot :%s"%snap_name)
    snapshot = SnapShotOps(snap_name,volobj=vol,create=True)
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
    #assert(status == 0)
       #restore using latest snapshot 
    status = vol.vol_rollback(snapshot,backup="true")
    assert(status == True)
    time.sleep(60)
       #cheking data integrity by rading the volumes data 
       #connecting the vol 
    logger.info("connecting the vol")
    status = host.connect_volume(vol)
    time.sleep(10)
    assert(status == 0)
    logger.info("Reading from the raw device")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_read([vol], host, kwargs)
    assert (status==0)
       #delete forensic snapshot
    status = snapshot.delete_all_forensic_snap()
    assert(status == True)
       # disconnect the vol to run teardown
    logger.info("disconnecting the vol from the host")
    status = host.disconnect_volume(vol)
    time.sleep(10)
    print("3. Vol restore after 5% IO on the vol:PASS")

################################ 4. Vol restore for degraded volumes 
@with_setup(setup=None, teardown=clear_zone_config)
@attr('vol_rollback_sanity')
def pds_rollback_degraded_vol():
        #objects initialization & Authentication
    log = PvltLogger(inspect.stack()[0][3],'INFO')
    logger = log.logger
    host = HostOps(HOST[0])
    fio = FioUtils()
    pvlLibHandle = pvlclient.New("2.0",CHASSIS_IP,logger=logger)
    result = pvlLibHandle.auth.login(user=CHASSIS_USER,password=CHASSIS_PASS)
        # defining variables
    name = MEDIA_GROUP_NAME
    md_type = MEDIA_GROUP_TYP
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
    time.sleep(10)
        # Power off one drive 
    mediaList = media_group.get_media_group_disk()
    media = [mediaList[0]]
    logger.info("Powering off drive : %s"%media)
    status = power_off_drive(media,pvlLibHandle)
    time.sleep(30)
        # write on the volume 
    logger.info("Starting overwrite on the vol-seq_write")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write([vol], host, kwargs)
    assert (status==0)
         #Creating a snapshot
    snap_name = "s1"
    logger.info("Creating a snapshot : %s"%snap_name)
    snapshot = SnapShotOps(snap_name,volobj=vol,create=True)
    assert(snapshot != None)
    time.sleep(10)
        # overwrite to 30% more 
    logger.info("Starting overwrite on the vol-seq_write")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xffff","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write([vol], host, kwargs)
    assert (status==0)
        # disconenct the vol 
    logger.info("disconnecting the vol from the host")
    status = host.disconnect_volume(vol)
    time.sleep(10)
    #assert(status == 0)
        # restore the volumes using s2 
    status = vol.vol_rollback(snapshot,backup="true")
    assert(status == True)
    time.sleep(60)
        # connect the vol & verify the data 
    logger.info("connecting the vol")
    status = host.connect_volume(vol) 
    time.sleep(10)
    assert(status == 0)
    logger.info("Reading from the raw device")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_read([vol], host, kwargs)
        # delete forensic snapshot
    status = snapshot.delete_all_forensic_snap()
    assert(status == True)
        # disconnect the vol to run teardown
    logger.info("disconnecting the vol from the host")
    status = host.disconnect_volume(vol)
    time.sleep(10)
    print("4. Vol restore for degraded volumes:PASS")

################################ 5. Vol restore for critical voluems 
@with_setup(setup=None, teardown=clear_zone_config)
@attr('vol_rollback_sanity')
def pds_rollback_critical_vol():
        #objects initialization & Authentication
    log = PvltLogger(inspect.stack()[0][3],'INFO')
    logger = log.logger
    host = HostOps(HOST[0])
    fio = FioUtils()
    pvlLibHandle = pvlclient.New("2.0",CHASSIS_IP,logger=logger)
    result = pvlLibHandle.auth.login(user=CHASSIS_USER,password=CHASSIS_PASS)
        # defining variables
    name = MEDIA_GROUP_NAME
    md_type = MEDIA_GROUP_TYP
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
    time.sleep(10)
        # assign the vol
    ports = get_two_port_diff_ctlr(ZONE)
    logger.info("Assigning vols ")
    status  = vol.assign_volume(ports,hostnqn=[])
    assert(status == True)
        # connet to the host
    status = host.connect_volume(vol)
    time.sleep(10)
    assert(status == 0)
        # write on the volume
    logger.info("Starting overwrite on the vol-seq_write")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write([vol], host, kwargs)
    assert (status==0)
        # poweroff 2  drive 
    mediaList = media_group.get_media_group_disk()
    media = [mediaList[0]] + [mediaList[1]]
    logger.info("Powering off drive : %s"%media)
    status = power_off_drive(media,pvlLibHandle)
    time.sleep(30)
        # take snapshot
    snap_name = "s2"
    logger.info("Taking snapshot :%s"%snap_name)
    snapshot = SnapShotOps(snap_name,volobj=vol,create=True)
    assert(snapshot != None)
        # overwrite on the volume
    logger.info("Starting overwrite on the vol-seq_write")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xffff","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write([vol], host, kwargs)
    assert (status==0)
        # poweron both the drive 
    logger.info("Powering ON drive : %s"%media)
    status = power_on_drive(media,pvlLibHandle) 
    time.sleep(120)
        # disconenct the vol
    logger.info("disconnecting the vol from the host")
    status = host.disconnect_volume(vol)
    time.sleep(10)
    #assert(status == 0)
        # restore the volumes using s2
    status = vol.vol_rollback(snapshot,backup="true")
    assert(status == True)
    time.sleep(60)
        # connect the vol & verify the data
    logger.info("connecting the vol")
    status = host.connect_volume(vol)
    time.sleep(10)
    assert(status == 0)
    logger.info("Reading from the raw device")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_read([vol], host, kwargs)
        # disconenct the vol
    logger.info("disconnecting the vol from the host")
    status = host.disconnect_volume(vol)
    time.sleep(10)
        # delete forensic snapshot
    status = snapshot.delete_all_forensic_snap()
    assert(status == True)
        # disconnect the vol to run teardown
    logger.info("disconnecting the vol from the host")
    status = host.disconnect_volume(vol)
    time.sleep(10)
    #assert(status == 0)

    print("5. Vol restore for critical voluems:PASS")
        
################################ 6. Vol restore with rebuild (2>1)
@with_setup(setup=None, teardown=clear_zone_config)
@attr('vol_rollback_sanity')
def pds_rollback_after_rebuild_21_10():
        #objects initialization & Authentication
    log = PvltLogger(inspect.stack()[0][3],'INFO')
    logger = log.logger
    host = HostOps(HOST[0])
    fio = FioUtils()
    pvlLibHandle = pvlclient.New("2.0",CHASSIS_IP,logger=logger)
    result = pvlLibHandle.auth.login(user=CHASSIS_USER,password=CHASSIS_PASS)
        # defining variables
    name = MEDIA_GROUP_NAME
    md_type = MEDIA_GROUP_TYP
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
    time.sleep(10)
        # assign the vol
    ports = get_two_port_diff_ctlr(ZONE)
    logger.info("Assigning vols ")
    status  = vol.assign_volume(ports,hostnqn=[])
    assert(status == True)
        # connet to the host
    status = host.connect_volume(vol)
    time.sleep(10)
    assert(status == 0)
        # Power off 2 drive
    mediaList = media_group.get_media_group_disk()
    media = [mediaList[0]] + [mediaList[1]]
    logger.info("Powering off drive : %s"%media)
    status = power_off_drive(media,pvlLibHandle)
    time.sleep(30)
        # write on the volume
    logger.info("Starting overwrite on the vol-seq_write")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write([vol], host, kwargs)
    assert (status==0)
        # Poweron one drive and start the rebuild
    media = [mediaList[0]]
    logger.info("Powering ON drive : %s"%media)
    status = power_on_drive(media,pvlLibHandle)
    time.sleep(120)
    logger.info("Start rebuild 2>1")
    status=media_group.synchronous_rebuild_media_group() 
        #Taking snaphost
    snap_name = "s2"
    logger.info("Taking snapshot :%s"%snap_name)
    snapshot = SnapShotOps(snap_name,volobj=vol,create=True)
    assert(snapshot != None)
        # overwrite on the volume
    logger.info("Starting overwrite on the vol-seq_write")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xffff","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write([vol], host, kwargs)
    assert (status==0)
      # disconenct the vol
    logger.info("disconnecting the vol from the host")
    status = host.disconnect_volume(vol)
    time.sleep(10)
    #assert(status == 0)
        # restore the volumes using s2
    status = vol.vol_rollback(snapshot,backup="true")
    assert(status == True)
    time.sleep(60)
        # connect the vol & verify the data
    logger.info("connecting the vol")
    status = host.connect_volume(vol)
    time.sleep(10)
    assert(status == 0)
    logger.info("Reading from the raw device")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_read([vol], host, kwargs)
        # delete forensic snapshot
    status = snapshot.delete_all_forensic_snap()
    assert(status == True)
        # Poweron second drive and start the rebuild
    media = [mediaList[1]]
    logger.info("Powering ON drive : %s"%media)
    status = power_on_drive(media,pvlLibHandle)
    time.sleep(120)
    logger.info("Start rebuild 1>0")
    status=media_group.synchronous_rebuild_media_group()
        # restore the volumes using s2
    status = vol.vol_rollback(snapshot.snap_id,backup="true")
    assert(status == True)
    time.sleep(60)
        # connect the vol & verify the data
    logger.info("connecting the vol")
    status = host.connect_volume(vol)
    time.sleep(10)
    assert(status == 0)
    logger.info("Reading from the raw device")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_read([vol], host, kwargs)
        # delete forensic snapshot
    status = snapshot.delete_all_forensic_snap()
    assert(status == True)
        # disconnect the vol to run teardown
    logger.info("disconnecting the vol from the host")
    status = host.disconnect_volume(vol)
    time.sleep(10)
    assert(status == 0)
    #assert(status == 0)
    print("6. Vol restore with rebuild (2>1):PASS")
################################ 7. Vol restore with rebuild (1>0)
    print("7. Vol restore with rebuild (1>0):PASS")

################################ 8. Vol restore with rebuild (2>0)
@with_setup(setup=None, teardown=clear_zone_config)
@attr('vol_rollback_sanity')
def pds_rollback_with_rebuild_20():
        #objects initialization & Authentication
    log = PvltLogger(inspect.stack()[0][3],'INFO')
    logger = log.logger
    host = HostOps(HOST[0])
    fio = FioUtils()
    pvlLibHandle = pvlclient.New("2.0",CHASSIS_IP,logger=logger)
    result = pvlLibHandle.auth.login(user=CHASSIS_USER,password=CHASSIS_PASS)
        #defining variables
    name = MEDIA_GROUP_NAME
    md_type = MEDIA_GROUP_TYP
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
    time.sleep(10)
        # assign the vol
    ports = get_two_port_diff_ctlr(ZONE)
    logger.info("Assigning vols ")
    status  = vol.assign_volume(ports,hostnqn=[])
    assert(status == True)
        # connet to the host
    status = host.connect_volume(vol)
    time.sleep(10)
    assert(status == 0)
        # powring off two drives 
    mediaList = media_group.get_media_group_disk()
    media = [mediaList[0]] + [mediaList[1]]
    logger.info("Powering OFF drive : %s"%media)
    status = power_off_drive([media_group.md_disk[1],media_group.md_disk[0]],pvlLibHandle)
    time.sleep(60)
        # write on the voluem
    logger.info("Starting overwrite on the vol-seq_write")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write([vol], host, kwargs)
    assert (status==0)
        #Taking snaphost
    snap_name = "s2"
    logger.info("Taking snapshot :%s"%snap_name)
    snapshot = SnapShotOps(snap_name,volobj=vol,create=True)
    assert(snapshot != None)
        # poweron the drives 
    logger.info("Powering ON drive : %s"%media)
    status = power_on_drive(media,pvlLibHandle)
    time.sleep(60)
        # start rebuild 
    logger.info("Start rebuild 2>0")
    status=media_group.synchronous_rebuild_media_group()
        # overwrite on the volume
    logger.info("Starting overwrite on the vol-seq_write")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xffff","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write([vol], host, kwargs)
    assert (status==0)
        # disconenct the vol
    logger.info("disconnecting the vol from the host")
    status = host.disconnect_volume(vol)
    time.sleep(10)
    #assert(status==0)
        # restore the volumes using s2
    status = vol.vol_rollback(snapshot,backup="true")
    assert(status == True)
    time.sleep(60)
        # connect the vol & verify the data
    logger.info("connecting the vol")
    status = host.connect_volume(vol)
    time.sleep(10)
    assert(status==0)
    logger.info("Reading from the raw device")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_read([vol], host, kwargs)
         # delete forensic snapshot
    status = snapshot.delete_all_forensic_snap()
    assert(status == True)
        # disconnect the vol to run teardown
    logger.info("disconnecting the vol from the host")
    status = host.disconnect_volume(vol)
    time.sleep(10)

    print("8. Vol restore with rebuild (2>0):PASS") 

################################ 9. Vol restore with clone is connected to the host
@with_setup(setup=None, teardown=clear_zone_config)
@attr('vol_rollback_sanity')
def pds_rollback_with_clone():
           #objects initialization & Authentication
    log = PvltLogger(inspect.stack()[0][3],'INFO')
    logger = log.logger
    host = HostOps(HOST[0])
    fio = FioUtils()
    pvlLibHandle = pvlclient.New("2.0",CHASSIS_IP,logger=logger)
    result = pvlLibHandle.auth.login(user=CHASSIS_USER,password=CHASSIS_PASS)
        # defining variables
    name = MEDIA_GROUP_NAME
    md_type = MEDIA_GROUP_TYP
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
    time.sleep(10)
        # assigning vol 
    ports = get_two_port_diff_ctlr(ZONE)
    logger.info("Assigning vols ")
    status  = vol.assign_volume(ports,hostnqn=[])
    assert(status == True) 
        # write on the volume
    logger.info("Starting overwrite on the vol-seq_write")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write([vol], host, kwargs)
    assert (status==0)
        # Creating a snapshot
    snap_name = "s1"
    logger.info("Creating a snapshot : %s"%snap_name)
    snapshot = SnapShotOps(snap_name,volobj=vol,create=True)
    assert(snapshot != None)
    time.sleep(10)
        # create clone
    #clone_list =[]
    clone_name = str(snap_name)+str("_c1")
    logger.info("Creating clone name : %s"%clone_name)
    cloneObj = CloneOps(clone_name,snapshot,create=True)
    #clone_list.append(cloneObj)
        # assign clone 
    logger.info("Assigning clone %s to contollers"%cloneObj.name)
    assign = cloneObj.assign_clone(ports,hostnqn=[])
        # connect clone to the host 
    logger.info("Connecting clone %s to the host"%cloneObj.name)
    status = host.connect_volume(cloneObj)
    time.sleep(10)
    assert(status==0)
        # start IO on the clone 
    logger.info("Staring write IO to the clone %s"%clone_name)
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write(clone_list, host, kwargs)
    assert (status==0)
       # overwrite on the volume
    logger.info("Starting overwrite on the vol-seq_write")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xffff","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write([vol], host, kwargs)
    assert (status==0)
        # disconenct the vol
    logger.info("disconnecting the vol from the host")
    status = host.disconnect_volume(vol)
    time.sleep(10)
    #assert(status == 0)
        # restore the volumes using s2
    status = vol.vol_rollback(snapshot,backup="true")
    assert(status == True)
    time.sleep(60) 
        # connect the vol & verify the data
    logger.info("connecting the vol")
    status = host.connect_volume(vol)
    time.sleep(10)
    assert(status == 0)
    logger.info("Reading from the raw device")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_read([vol], host, kwargs)
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
    
    print("9. Vol restore with clone is connected to the host:PASS")

################################ delete s2 and its child snapshot
'''
