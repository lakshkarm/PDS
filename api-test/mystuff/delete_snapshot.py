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
from lib.storage.CLEARCONFIG import clear_config

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


def pds_vol_rollback_sanity():
    pvlLibHandle = pvlclient.New("2.0",CHASSIS_IP,logger=logger)
    result = pvlLibHandle.auth.login(user=CHASSIS_USER,password=CHASSIS_PASS)
    obj = clear_config(pvlLibHandle,ZONE)
    snap_list = obj.snapshots
    forensic_snp_list = []  
    for i in snap_list:
        if "forensicParentSnapshot" in i:
            if i["mediaGrpName"] == MEDIA_GROUP_NAME and i["forensicParentSnapshot"] == "s1":
               a = i["name"] 
               snap =a.encode('ascii')
               forensic_snp_list.append(snap) 
    print forensic_snp_list
    
    # delete snaphsot 
    snapshot = pvlLibHandle.storage.delete_snapshot(forensic_snp_list[0],wait=True)
    if snapshot.status != 0 :
        print("failed to delete snaphsot")
        sys.exit("failed to delete snapshot")
    print("snapshot deleted successfully")
  

pds_vol_rollback_sanity()

