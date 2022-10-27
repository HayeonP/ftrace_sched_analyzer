#!/bin/bash

if [ ! -d "./temp" ]; then
    mkdir temp    
fi

rm -r temp/*

sshpass -p "nvidia" scp -r nvidia@192.168.0.104:/home/nvidia/git/instance_contention_research/log/ftrace_log.txt ./temp
sshpass -p "nvidia" scp -r nvidia@192.168.0.104:/home/nvidia/git/instance_contention_research/log/pid_info.json ./temp
sshpass -p "nvidia" scp -r nvidia@192.168.0.104:/home/nvidia/git/instance_contention_research/log/response_time/*.csv ./temp
sshpass -p "nvidia" scp -r nvidia@192.168.0.104:/home/nvidia/git/instance_contention_research/src/synthetic_task_generator/scripts/configs.json ./temp