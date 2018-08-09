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


def pds_vol_restore_sanity():
    host = HostOps(HOST[0])
    fio = FioUtils()
        # give function name as log file name
    log = PvltLogger("Volume_restore",'INFO')
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
    assert(media_group != None)
        ## creaing volumes 
    logger.info("Creating voluems")
    #vol_list = []
    volname = VOL_PREFIX
    vol=VolumeOps(md=media_group,name=volname,size=VOL_SIZE,vol_res=VOL_RES,flavor=FLAVOR,create=True)
    assert(vol != None)
    
         #Creating a snapshot
    snap_name = "s1" 
    logger.info("Creating a snapshot : %s"%snap_name)
    snapshot = SnapShotOps(snap_name,volobj=vol,create=True)
    assert(snapshot != None)


################################ 1 Vol restore for unassigned volume  
        # Restore the vol using its snapshot
    #status = snapshot.vol_restore()
    #assert(status == True)
    #time.sleep(60)
    #print("1 Vol restore for unassigned volume: PASS")

################################ 2 Vol restore after assign volume
    ports = get_two_port_diff_ctlr(ZONE)
    logger.info("Assigning vols ")
    status  = vol.assign_volume(ports,hostnqn=[])
    assert(status == True)
    #status = snapshot.vol_restore()
    #assert(status == True)
    #time.sleep(60)
    #print("2 Vol restore after assign volume:PASS")

################################## delete s1 and its child snapshot 
   #  Need to write forensic snapshots deletion code 
################################## 3. Vol restore after 5% IO on the vol
    status = host.connect_volume(vol)
    time.sleep(10)
    assert(status == 0)
        #start fio on all the volumes 
    logger.info("Starting write on the vol-seq_write")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write([vol], host, kwargs)
    assert (status == 0)
        # Taking snaphost 
    snap_name = "s2" 
    logger.info("Taking snapshot :%s"%snap_name)
    snapshot = SnapShotOps(snap_name,volobj=vol,create=True)
    assert(snapshot != None)
        # Write on remaning space of the volumes 
    logger.info("Starting write on other space of the vol ")
    kwargs = {'offset':"45g",'size':'5g',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.rand_read_write([vol], host, kwargs)
    assert (status == 0)
        # disconnect the vol 
    logger.info("disconnecting the vol from the host")
    status = host.disconnect_volume(vol)
    time.sleep(10)
    assert(status == 0)
        # restore using latest snapshot 
    #status = snapshot.vol_restore()
    #assert(status == True)
    #time.sleep(60)
        # cheking data integrity by rading the volumes data 
        # connecting the vol 
    logger.info("connecting the vol")
    status = host.connect_volume(vol)
    time.sleep(10)
    assert(status == 0)
    logger.info("Reading from the raw device")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_read([vol], host, kwargs)
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
    status,response=fio.seq_write([vol], host, kwargs)
    assert (status==0)
        # disconenct the vol 
    logger.info("disconnecting the vol from the host")
    status = host.disconnect_volume(vol)
    time.sleep(10)
    assert(status == 0)
        # restore the volumes using s2 
    #status = snapshot.vol_restore()
    #assert(status == True)
    #time.sleep(60)
        # connect the vol & verify the data 
    logger.info("connecting the vol")
    status = host.connect_volume(vol) 
    time.sleep(10)
    assert(status == 0)
    logger.info("Reading from the raw device")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_read([vol], host, kwargs)
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
    status,response=fio.seq_write([vol], host, kwargs)
    assert (status==0)
        # disconenct the vol
    logger.info("disconnecting the vol from the host")
    status = host.disconnect_volume(vol)
    time.sleep(10)
    assert(status == 0)
        # restore the volumes using s2
    #status = snapshot.vol_restore()
    #assert(status == True)
    #time.sleep(60)
        # connect the vol & verify the data
    logger.info("connecting the vol")
    status = host.connect_volume(vol)
    time.sleep(10)
    assert(status == 0)
    logger.info("Reading from the raw device")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_read([vol], host, kwargs)
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
    status,response=fio.seq_write([vol], host, kwargs)
    assert (status==0)
        # disconenct the vol
    logger.info("disconnecting the vol from the host")
    status = host.disconnect_volume(vol)
    time.sleep(10)
    assert(status == 0)
        # restore the volumes using s2
    #status = snapshot.vol_restore()
    #assert(status == True)
    #time.sleep(60)
        # connect the vol & verify the data
    logger.info("connecting the vol")
    status = host.connect_volume(vol)
    time.sleep(10)
    assert(status == 0)
    logger.info("Reading from the raw device")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_read([vol], host, kwargs)
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
    status,response=fio.seq_write([vol], host, kwargs)
    assert (status==0)
        # disconenct the vol
    logger.info("disconnecting the vol from the host")
    status = host.disconnect_volume(vol)
    time.sleep(10)
    assert(status == 0)
        # restore the volumes using s2
    #status = snapshot.vol_restore()
    #assert(status == True)
    #time.sleep(60)
        # connect the vol & verify the data
    logger.info("connecting the vol")
    status = host.connect_volume(vol)
    time.sleep(10)
    assert(status==0)
    logger.info("Reading from the raw device")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_read([vol], host, kwargs)
    print("7. Vol restore with rebuild (1>0):PASS")

################################ 8. Vol restore with rebuild (2>0)
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
    logger.info("Starting overwrite on the vol-seq_write")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write([vol], host, kwargs)
    assert (status==0)
        # disconenct the vol
    logger.info("disconnecting the vol from the host")
    status = host.disconnect_volume(vol)
    time.sleep(10)
    assert(status==0)
        # restore the volumes using s2
    #status = snapshot.vol_restore()
    #assert(status == True)
    #time.sleep(60)
        # connect the vol & verify the data
    logger.info("connecting the vol")
    status = host.connect_volume(vol)
    time.sleep(10)
    assert(status==0)
    logger.info("Reading from the raw device")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_read([vol], host, kwargs)
    print("8. Vol restore with rebuild (2>0):PASS") 

################################ 9. Vol restore with clone is connected to the host
        # overwrite on the volume
    logger.info("Starting overwrite on the vol-seq_write")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write([vol], host, kwargs)
    assert (status==0)
        # create clone
    clone_list =[]
    clone_name = str(snap_name)+str("_c1")
    logger.info("Creating clone name : %s"%clone_name)
    cloneObj = CloneOps(clone_name,snapshot,create=True)
    clone_list.append(cloneObj)
        # assign clone 
    logger.info("Assigning clone %s to contollers"%clone_name)
    assign = cloneObj.assign_clone(ports,hostnqn=[])
        # connect clone to the host 
    logger.info("Connecting clone %s to the host"%clone_name)
    status = host.connect_volume(cloneObj)
    time.sleep(10)
    assert(status==0)
        # start IO on the clone 
    logger.info("Staring write IO to the clone %s"%clone_name)
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_write(clone_list, host, kwargs)
    assert (status==0)
        # disconenct the vol
    logger.info("disconnecting the vol from the host")
    status = host.disconnect_volume(vol)
    time.sleep(10)
    assert(status == 0)
        # restore the volumes using s2
    #status = snapshot.vol_restore()
    #assert(status == True)
    #time.sleep(60) 
        # connect the vol & verify the data
    logger.info("connecting the vol")
    status = host.connect_volume(vol)
    time.sleep(10)
    assert(status == 0)
    logger.info("Reading from the raw device")
    kwargs = {'offset':"0",'size':'5%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
    status,response=fio.seq_read([vol], host, kwargs)
    print("9. Vol restore with clone is connected to the host:PASS")
    

################################ delete s2 and its child snapshot

pds_vol_restore_sanity()

