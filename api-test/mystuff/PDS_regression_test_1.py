#!/usr/bin/python -B
import random,sys
import inspect
import logging
import json
import pvlclient
import time,os
import traceback
from os import environ as env
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
    ControllerOps, 
)

from lib.system.DRIVEUTILS import (
    get_active_drive_count
    )
from lib.storage.CLEARCONFIG import(
    clear_zone_config
)

from lib.misc.MISCOPS import (
    wait_till_task_complete,
    run,
    sleep_p,
    setup_func
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
        logger.info("Creating volumes")
        vol=VolumeOps(md=media_group,name=volname,size=VOL_SIZE,vol_res=VOL_RES,flavor=FLAVOR,create=True)
        vol_list.append(vol)
        assert(vol != None)
    return media_group,vol_list

################################ 1.Online vol IO test 
@with_setup(setup=None, teardown=clear_zone_config)
@attr('raid6','sanity')
def pds_online_vol_IO_sanity():
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
        kwargs = {'offset':"0",'size':'50%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1,
                    "bs":"64k"}
        status,response=fio.seq_write(vol_list, host, kwargs)
        assert (status == 0)
    
 #    # start FIO thread here
 #
 #    temp_file_path = "%s/tmp/run_fio.%s"%(env['TESTDIR'] ,os.getpid())
 #    cmd = "touch %s "%temp_file_path
 #    run(cmd)
 #    proc=multiprocessing.Process(target=fio.infinite_fio,args=(vol_list, host, temp_file_path))
 #    proc.start()
 #    logger.info('Fio process id code %s'%proc.pid)
 #    sleep_p(60)
 #    if proc.is_alive():
 #        sleep_p(60)
 #    else:
 #        logger.error('Fio process failed %s'%proc.pid)
 #        assert(proc.exitcode==0)
 #
 #    cmd = "rm -f %s "%temp_file_path
 #    run(cmd)
 #    if proc.is_alive():
 #        proc.join()
 #    print"fio run finished"

 #    ## start graceful FOFB while the IOs are running
 #    #start fio on all the volumes
 #    p1 = multiprocessing.Process(name="StartFio",target=startIO)
 #    logger.info("starting IOs just in parallel with FOFB operations")
 #    p1.start()
 #    time.sleep(5)

    def rebuilds_func():
        # starting one driver rebuild
        # Power off one drive
        mediaList = media_group.get_media_group_disk()
        for i in range(1):
            media = [mediaList[i]]
            logger.info("Powering off drive : %s"%media)
            status = power_off_drive(media,pvlLibHandle)
            time.sleep(30)

            # poweron the same drive
            logger.info("Powering ON drive : %s"%media)
            status = power_on_drive(media,pvlLibHandle)
            time.sleep(60)

            # start rebuild with io
            logger.info("Start rebuild 1>0")
            #status=media_group.synchronous_rebuild_media_group()
            #status=media_group.asynchronous_rebuild_media_group()
            assert(media_group.synchronous_rebuild_media_group())
            time.sleep(60)

        ## starting 2 drive rebuild
        for i in range(10):
            media = [mediaList[0]] + [mediaList[1]]
            logger.info("Powering off drive : %s"%media)
            status = power_off_drive(media,pvlLibHandle)
            time.sleep(60)

            # poweron the drive again
            logger.info("Powering ON drive : %s"%media)
            status = power_on_drive(media,pvlLibHandle)
            time.sleep(60)

            # start async-rebuild with io
            logger.info("Start rebuild 1>0")
            #status=media_group.synchronous_rebuild_media_group()
            #status=media_group.asynchronous_rebuild_media_group()
            assert(media_group.synchronous_rebuild_media_group())
            time.sleep(60)

        ## 2>1 && 1>0 rebuild
          #mediaList = media_group.get_media_group_disk()
            media = [mediaList[2]] + [mediaList[3]]
            logger.info("Powering off drive : %s"%media)
            status = power_off_drive(media,pvlLibHandle)
            time.sleep(60)
          # Poweron one drive and start the rebuild
            media = [mediaList[2]]
            logger.info("Powering ON drive : %s"%media)
            status = power_on_drive(media,pvlLibHandle)
            time.sleep(60)

            # start rebuild with IO
            logger.info("Start rebuild 2>1")
            #status=media_group.synchronous_rebuild_media_group()
            status=media_group.asynchronous_rebuild_media_group()
            time.sleep(60)
        if proc.is_alive():
            # Poweron second drive and start the rebuild
            media = [mediaList[3]]
            logger.info("Powering ON drive : %s"%media)
            status = power_on_drive(media,pvlLibHandle)
            time.sleep(60)
            # start async-rebuild
            logger.info("Start rebuild 1>0")
            #status=media_group.synchronous_rebuild_media_group()
            #status=media_group.asynchronous_rebuild_media_group()
            assert(media_group.synchronous_rebuild_media_group())
            time.sleep(60)

    def graceful_fofb():
        logger.info("Starting graceful FOFB power-off/on")
        for i in range(1):
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
    
    def resize_vol(vol_list):
        for vol in vol_list:
            logger.info(" vol size before resize operation is : %s"%vol.vol_size)
            status =  host.get_vol_size(vol)
            print status

            # vol growing by 100G
            logger.info("follwing vol is getting grown by 100GB : %s"%vol.name)
            status = vol.volume_grow()
            assert(status == True)

            ## rescan the vol on the host
            status = host.get_added_vol_capacity(vol)
            #printing new size of the vol
            logger.info(" vol size after resize operation is : %s"%vol.vol_size)
            status = host.get_vol_size(vol)
            print status

    
#start FIO thread here
    temp_file_path = "%s/tmp/run_fio.%s"%(env['TESTDIR'] ,os.getpid())
    cmd = "touch %s "%temp_file_path
    run(cmd)
    proc=multiprocessing.Process(target=fio.infinite_fio,args=(vol_list, host, temp_file_path))
    proc.start()
    logger.info('Fio process id code %s'%proc.pid)
    sleep_p(60)
    if proc.is_alive():
        sleep_p(60)
    else:
        logger.error('Fio process failed %s'%proc.pid)
        assert(proc.exitcode==0)

    try:
        
#1# now starting graceful FOFB operations 
        logger.info("Starting graceful FOFB power-off/on")
        if proc.is_alive():
            graceful_fofb()
            
#2# Now perfrom 1>0 || 2>0 || 2>1,1>0 rebuild
        if proc.is_alive():
            rebuilds_func()

#3# now starting graceful FOFB operations
        logger.info("Starting graceful FOFB power-off/on")
        if proc.is_alive():
            graceful_fofb()

#00# take the clone and overwrite on it  <<< i will implement this section after vol resize loop 

 
#4# grow vol and do the stuffs 
        if proc.is_alive():
            resize_vol(vol_list)

#5# Now again do the FOFB operations 
        logger.info("Starting graceful FOFB power-off/on")
        if proc.is_alive():
           graceful_fofb()

#6# Now perfrom 1>0 || 2>0 || 2>1,1>0 rebuild 
        if proc.is_alive():
           rebuilds_func()

#7# Start FOFB
        if proc.is_alive():
           graceful_fofb()

#8# Now perfrom 1>0 || 2>0 || 2>1,1>0 rebuild
        if proc.is_alive():
            rebuilds_func()

    except Exception as E:
        logger.error('Stack trace for failure \n%s\n'%traceback.format_exc())
        raise E
        
    finally:
        cmd = "rm -f %s "%temp_file_path
        run(cmd)
        if proc.is_alive():
            proc.join()
        code = proc.exitcode
        if code != 0 :
            logger.error('Fio failed on volumes ')
            assert(code == 0 )
