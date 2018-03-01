import argparse, sys, time, multiprocessing, datetime
import target_defs


req_keys = ["id","flavor","displayType","reserved","size","nqn","snapCount","state","display_state","dev_name","displayState", "mediaGrpId", "mediaGrpState", "snapDeletingCount", "zone", "parentVolName", "diskType"]
def print_format(data, flag=0):
	for k,v in data.iteritems():
		if flag and k not in req_keys:
			continue
		print "\t%s :: %s"%(k,v)

	print

_api = target_defs.TARGET_API(sys.argv[1])
_api.get_details()


print "============================================================="
print_format(_api.get_given_parent_obj_info('chassis', 'baseinfo'))
op = _api.get_given_parent_obj_info('chassis', 'upgrade-summary')
for l in op:
	print_format(l)

for mg in _api._dict['mg_details'].keys(): 
	mg_id = _api._dict['mg_details'][mg]['mg_id']

	print_format(_api.get_given_parent_obj_info('storage/mediagroups', '%s/summary'%mg_id))
	op = _api.get_given_parent_obj_info('storage/volumes',  'all')
	for vol in op:
		if vol['mediaGrpId'] == mg_id:
			print '+++++++++++++++++++%s+++++++++++++++'%vol['name']
			print_format(vol, 1)
	

print "============================================================="


