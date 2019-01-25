#!/usr/bin/python -B
import random
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

def pds_create_mediagroup():
    global logger
    global pvlLibHandle
    log = PvltLogger("rebuild_operation",'INFO')
    logger = log.logger

    name = MEDIA_GROUP_NAME

    pvlLibHandle = pvlclient.New("2.0",CHASSIS_IP,logger=logger)
    result = pvlLibHandle.auth.login(user=CHASSIS_USER,password=CHASSIS_PASS)

    drv_cnt = get_active_drive_count(ZONE,pvlLibHandle)
    logger.info(ZONE)
    logger.info(drv_cnt)
    if drv_cnt < 9 :
        logger.error('Not sufficient drives active drive count=%s'%drv_cnt)
        #assert(drv_cnt > 8 )

    md_type = 'RAID-0 (18+0)' if drv_cnt == 18 else 'RAID-6 (6+2+1)'

    md = MediaGroupOps(pvlLibHandle, name, ZONE, md_type,create=False)
    media_group = md
    assert(md != None)
    ## deleting mediaGroup
     #print("now deleting the mg in 5 sec")
     #time.sleep(5)
     #media_group.delete_mediagroup()

    ## creaing volumes 
    vol_list = []
    for i in range(2):
        volname = str(VOL_PREFIX )+str("_")+str(i)
        vol=VolumeOps(md=media_group,name=volname,size=VOL_SIZE,vol_res=VOL_RES,flavor=FLAVOR,create=True)
        vol_list.append(vol)
    #print("following volumes have been created : %s"%vol_list)
    #'''
    ## assign volume
    ports = get_two_port_diff_ctlr(ZONE)
    for v in vol_list:
         assign=v.assign_volume(ports)
    #connecting  voluems to the host  
    for v in vol_list:
        host = HostOps(HOST[0])
        status=host.connect_volume(v)
        #assert(status==0)
    # stert fio on all the volumes 
    '''
    def startIO():
        p1 = multiprocessing.current_process()
        logger.info("Starting : %s : %s"%(p1.name,p1.pid))
        print "Starting :",p1.name,p1.pid
        host = HostOps(HOST[0])  # getting host object
        fio = FioUtils()         # getting fio object
        kwargs = {'size':'100%',"verify_pattern":"0xABCD","verify_interval":4096,"do_verify":1}
        #status,response=fio.rand_read_write(vol_list, host, kwargs)
        status,response=fio.seq_write(vol_list, host, kwargs)
        assert (status==0)
    
     
    ### getting used disks in the mediaGroup
    def rebuld_loop(no_of_iterations):
        p2 = multiprocessing.current_process()
        logger.info("Starting : %s : %s"%(p2.name,p2.pid))
        print "Starting",p2.name,p2.pid
        for i in range(no_of_iterations):
            mediaList = media_group.get_media_group_disk()
            media = [mediaList[0]]
            status = power_off_drive(media,pvlLibHandle)   
            time.sleep(30)
            status = power_on_drive(media,pvlLibHandle)
            time.sleep(120)
            status=media_group.rebuild_media_group()
            logger.info(status)
            time.sleep(60)
            #assert (status==0)
    
    p1 = multiprocessing.Process(name="StartFio",target=startIO)
    p1.deamon = False
    p2 = multiprocessing.Process(name="2_drive_rebuld",target=rebuld_loop,args=(10,))
    p2.deamon = True

    p1.start()
    p2.start()
    p1.join()
    p2.join()
    '''

pds_create_mediagroup()
