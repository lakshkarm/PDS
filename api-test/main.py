import helper
import time,argparse,sys,multiprocessing,json

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
#parser = argparse.ArgumentParser()
parser.add_argument('-r','--rebuild',dest='rebuild',type=int,action='store',default=0,choices=[0,1,2], 
                    help='you can chose 1 for 1-drive or 2  2-drive rebuild along with this flag')
parser.add_argument('-s', action='store_true', default=False, dest='rand', help='Random flag')
parser.add_argument('-c','--copy',dest='copy',type=int,action='store',choices=[1,2,3],
                    help="use this option to create snap/clone 1=snapshot ,2 snap&clone both ,3-create both and assgined/connect")
parser.add_argument('-o','--create',dest='create',action='store_true',default=False,help='Use this flag to create mg or volumes')
args = parser.parse_args()
print args

MG_NAME = "manishmg1"
NO_OF_VOLUMES = 16
CTRL_1_IP = "192.168.23.5"
CTRL_2_IP = "192.168.7.2"


if args.rebuild == 1:
    print("starting one drive rebuld")
    device_list =  helper.used_media_in_mg(MG_NAME)
    print device_list
    rebuild_no = 0
    for i in device_list:
        helper.drive_poweroff(i)
        logger.info("wating for 60 sec to confirm the disk status ")
        time.sleep(60)
        logging.info("drive got powered off successfully")
        helper.drive_poweron(i)
        time.sleep(120)
        if check_disk_state(str(i),MG_NAME) == "Active":
            print "Disk is Active now"
            logging.info("starting rebuild")
            helper.rebuild_media_grp(MG_NAME)
            logger.info("next rebuild will start in 120 sec")
            time.sleep(120)
            logger.info("Rebuild iteration %s completed "%rebuild_no)
        rebuild_no += 1
elif args.rebuild == 2:
    print("2 drive rebuld function not yet implemented")
else:
    print("Rebuild type is not choosen")


### some functions 
def create_snap_clone(c=None):
    vol_list = helper.get_existing_vols()
    print vol_list
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

#####

if args.copy == 1:
    print("only snapshots will be taken now ")
    snap_list = create_snap_clone()
elif args.copy == 2:
    print("both snap/clones will be taken")
    snap_list,clone_list = create_snap_clone(1)
elif args.copy == 3:
    snap_list,clone_list = create_snap_clone(1)
    #now assigning and conneting all for them 
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

if args.create:
    	vol_list = []
        def create_assign_vol(size, stripe , name, reservation, md_grp, flavor,IP1,IP2=None):
	    helper.create_vol(size, stripe , name, reservation, md_grp, flavor)
	    #create_vol('100', '4',vol, str(100), MG_NAME, 'INSANE')
	    helper.assign(name,IP1,IP2)
    	def multiproc(no):
		volname= 'ML_TV'
		for i in range(no):
		    vol = volname+"_"+str(i)
		    #p = multiprocessing.Process(target=create_assign_vol,args=('120', '4',vol, str(70), MG_NAME, 'INSANE',CTRL_1_IP,CTRL_2_IP))
		    p = multiprocessing.Process(target=create_assign_vol,args=('120', '4',vol, str(70), MG_NAME, 'INSANE',CTRL_1_IP))
		    p.start()
		    p.join()
		    vol_list.append(vol)
	## starting volume creation
	multiproc(NO_OF_VOLUMES)
	

'''
if args.interval:
##  list all the existing volumes 
    vol_list = helper.get_existing_vols()
    print vol_list

if args.rand:
    print "hello this is random message"


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
'''
