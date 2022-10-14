#!/bin/bash

sshpass -p "nvidia" scp -r nvidia@192.168.0.104:/home/nvidia/git/instance_contention_research/log/ftrace_log.txt .
sshpass -p "nvidia" scp -r nvidia@192.168.0.104:/home/nvidia/git/instance_contention_research/log/pid_info.json .
sshpass -p "nvidia" scp -r nvidia@192.168.0.104:/home/nvidia/git/instance_contention_research/log/response_time/*.csv .
sshpass -p "nvidia" scp -r nvidia@192.168.0.104:/home/nvidia/git/instance_contention_research/src/synthetic_task_generator/scripts/configs.json .