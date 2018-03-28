import helper
import time

##  list all the existing volumes 
vol_list = helper.get_existing_vols()
print vol_list

def create_snap_clone(c=None):
    snap_list = []
    if c == 1:
        for i in vol_list:
            count = 1
            vol_id = helper.get_object_id('volume', i)
            snap_name = "snap"+str(count)+"_"+str(i)
            helper.create_copy(vol_id,"Snapshot",snap_name)
            snap_list.append(snap_name)
    else:
        for i in vol_list:
            count = 1
            vol_id = helper.get_object_id('volume', i)
            snap_name = "snap"+str(count)+"_"+str(i)
            helper.create_copy(vol_id,"Snapshot",snap_name)
            time.sleep(30)
            snap_list.append(snap_name)
            count+=1

#create_snap_clone()

