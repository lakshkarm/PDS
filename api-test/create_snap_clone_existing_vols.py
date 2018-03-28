import helper
import time

CTRL_1_IP = "192.168.6.1"
CTRL_2_IP = "192.168.7.2"
#logger = helper.advance_logger()
##  list all the existing volumes 
vol_list = helper.get_existing_vols()
print vol_list

def create_snap_clone(c=None):
    snap_list = []
    clone_list = []
    if c == 1:
        for i in vol_list:
            count = 1
            vol_id = helper.get_object_id('volume', i)
            snap_name = "snap"+str(count)+"_"+str(i)
            helper.create_copy(vol_id,"Snapshot",snap_name)
            time.sleep(30)
            snap_id = helper.get_object_id("snapshot", snap_name)
            clone_name = "C"+str(count)+"_"+str(snap_name)
            helper.create_copy(snap_id,"Clone",clone_name,90)
            time.sleep(30)
            snap_list.append(snap_name)
            clone_list.append(clone_name)
            count+=1
        return(snap_list,clone_list)
    else:
        for i in vol_list:
            count = 1
            vol_id = helper.get_object_id('volume', i)
            snap_name = "snap"+str(count)+"_"+str(i)
            helper.create_copy(vol_id,"Snapshot",snap_name)
            time.sleep(30)
            snap_list.append(snap_name)
            count+=1
        return(snap_list)


snap_list,clone_list = create_snap_clone(1)
'''
for snap_name in snap_list:
    logger.info("Assigning %s to the controllers"%snap_name)
    helper.assign(snap_name,CTRL_1_IP,CTRL_2_IP)
    time.sleep(6)
## Assign clones to the controllers
for clone_name in clone_list:
    logger.info("Assigning %s to the controllers"%clone_name)
    helper.assign(clone_name,CTRL_1_IP,CTRL_2_IP)
    time.sleep(10)
    #logger.info("Connecting %s to the host-%s"%(clone_name,HOST_IP))
    #connect_host(CTRL_IPS, HOST_IP, clone_name)

'''
