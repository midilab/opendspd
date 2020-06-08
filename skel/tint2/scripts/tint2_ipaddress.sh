#!/bin/bash

eth=$(ip a s eth0 | grep -w 'inet' | awk 'NR==1{print $2}') 
wlan=$(ip a s wlan0 | grep -w 'inet' | awk '{print $2}')

printf 'eth: %8s\nwlan: %8s ' "$eth" "$wlan"
