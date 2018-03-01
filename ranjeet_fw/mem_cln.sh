#!/bin/bash -x
while true; do
    echo 3 > /proc/sys/vm/drop_caches
	sleep 7
    echo 2 > /proc/sys/vm/drop_caches
	sleep 9
    echo 1 > /proc/sys/vm/drop_caches
    sleep 13
    echo "----------------------------------------------------"
    free -h
    echo "----------------------------------------------------"
done
