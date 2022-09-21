from cmath import log
import sched
import matplotlib
import numpy as np
from parse import compile
import copy
import json
import os
import glob
import csv

############### TODO ###############
# core number of your computer
CPU_NUM = 12
# analyze autoware node only
ONLY_AUTOWARE = True
####################################

# 
TIME = 0
PREV_COMM = 1
PREV_PID = 2
PREV_PRIO = 3
PREV_STAT = 4
NEXT_COMM = 5
NEXT_PID = 6
NEXT_PRIO = 7
NONE = -100

#
count_ = 0
def parse_ftrace_log(file, process_name):
    func_pattern = compile("{}[{}] {} {}: {}: {}")
    sched_switch_pattern = compile("{}[{}] {} {}: {}: prev_comm={} prev_pid={} prev_prio={} prev_state={} ==> next_comm={} next_pid={} next_prio={}")

    per_cpu_info = {}
    
    for i in range(CPU_NUM):
        per_cpu_info['cpu'+str(i)] = []

    if not ONLY_AUTOWARE:
        process_name = []

    while True:
        line = file.readline()
        if not line:
            break
        
        result = func_pattern.parse(line)
        
        if result != None:
            if result[4] == 'sched_switch':
                sched_parse_result = sched_switch_pattern.parse(line)

                per_cpu_info['cpu' + str(int(sched_parse_result[1]))].append((float(sched_parse_result[3]), sched_parse_result[5], int(sched_parse_result[6]),
                                                                              int(sched_parse_result[7]), sched_parse_result[8], sched_parse_result[9],
                                                                              int(sched_parse_result[10]), int(sched_parse_result[11])))

                if not ONLY_AUTOWARE:
                    already_exist = False
                    for i in range(len(process_name)):
                        if process_name[i] == sched_parse_result[5]:
                            already_exist = True
                    if not already_exist:
                        if not sched_parse_result[5][0:7] == "swapper":
                            process_name.append(sched_parse_result[5])
    
    return per_cpu_info, process_name

def update_per_process_info(cpu_info, process_name):
    global count_
    per_cpu_info, per_cpu_start_info = {}, {}
    per_process_info, per_process_start_info = {}, {}

    for i in range(len(process_name)):
        per_process_info[process_name[i]] = []
        # (is_start, start_time, pid)
        per_process_start_info[process_name[i]] = [False, 0.0, 0]

    for i in range(CPU_NUM):
        per_cpu_info['cpu'+str(i)] = copy.deepcopy(per_process_info)
        per_cpu_start_info['cpu'+str(i)] = per_process_start_info

    max_time = 0.0
    for i in range(CPU_NUM):
        for j in range(len(cpu_info['cpu'+str(i)])):
            for k in range(len(process_name)):
                if cpu_info['cpu'+str(i)][j][NEXT_COMM] == process_name[k]:
                    per_cpu_start_info['cpu'+str(i)][process_name[k]][0] = True
                    per_cpu_start_info['cpu'+str(i)][process_name[k]][1] = cpu_info['cpu'+str(i)][j][TIME]
                    per_cpu_start_info['cpu'+str(i)][process_name[k]][2] = cpu_info['cpu'+str(i)][j][NEXT_PID]

                if cpu_info['cpu'+str(i)][j][PREV_COMM] == process_name[k]:
                    if cpu_info['cpu'+str(i)][j][PREV_PID] == per_cpu_start_info['cpu'+str(i)][process_name[k]][2]:
                        if per_cpu_start_info['cpu'+str(i)][process_name[k]][0]:
                            per_cpu_start_info['cpu'+str(i)][process_name[k]][0] = False
                            
                            process_info = {}
                            process_info['Count'] = count_
                            process_info['PID'] = per_cpu_start_info['cpu'+str(i)][process_name[k]][2]
                            process_info['StartTime'] = per_cpu_start_info['cpu'+str(i)][process_name[k]][1]
                            process_info['EndTime'] = cpu_info['cpu'+str(i)][j][TIME]
                            process_info['Instance'] = NONE

                            per_cpu_info['cpu'+str(i)][process_name[k]].append(process_info)

                            count_ = count_ + 1
                
                if max_time < cpu_info['cpu'+str(i)][j][TIME]:
                    max_time = cpu_info['cpu'+str(i)][j][TIME]

    return per_cpu_info, max_time

def filtering_process_info(per_cpu_info):
    for i in range(CPU_NUM):
        for j in range(len(process_name)):
            if len(per_cpu_info['cpu'+str(i)][process_name[j]]) == 0:
                per_cpu_info['cpu'+str(i)].pop(process_name[j])
    
    return per_cpu_info

def create_filtering_option(process_name):
    filtering_option = {}
    for i in range(len(process_name)):
        filtering_option[process_name[i]] = True
    return filtering_option

def str_match_from_front(str1, str2):
    for i in range(min(len(str1), len(str2))):
        if str1[i] != str2[i]: return False
    
    return True

def get_node_instance_info(log_file):
    reader = csv.reader(log_file)
    next(reader)
    
    node_instance_info = []
    
    pid = NONE
    start = NONE
    end = NONE
    instance = NONE
    prev_instance = NONE
    
    for line in reader:
        if pid == NONE: pid = line[1]
        cur_start = line[2]
        cur_end = line[3]
        cur_instance = line[4]
        
        if instance == NONE:
            start = cur_start
            end = cur_end
            instance = cur_instance    
        
        if prev_instance != 1:        
            if cur_instance == prev_instance:
                end = cur_end
            else:
                node_instance_info.append({'instance':instance, 'start':float(start), 'end':float(end)})
                instance = NONE
        
        prev_instance = line[4]
    
    return pid, node_instance_info
    

def get_e2e_instance_info(log_path):
    log_file = open(log_path)
    reader = csv.reader(log_file)
    next(reader)

    e2e_instance_info = []
    
    instance = NONE
    start = NONE
    end = NONE

    for line in reader:
        instance = line[0]
        start = line[1]
        end = line[2]

        e2e_instance_info.append({'instance':int(instance), 'start':float(start), 'end':float(end)})

    return e2e_instance_info

def add_instance_info(per_cpu_info, autoware_log_dir, autoware_e2e_log_path):
    e2e_instance_info = get_e2e_instance_info(autoware_e2e_log_path)

    for log_path in glob.glob(os.path.join(autoware_log_dir, '*.csv')):
        node_name = log_path.split('/')[-1].split('.')[0]
        
        for core in per_cpu_info:
            for name in per_cpu_info[core]:
                if not str_match_from_front(name, node_name): continue
                
                for sched_info in per_cpu_info[core][name]:
                    if sched_info['Instance'] != NONE: continue                
                    
                    for i, instance_info in enumerate(e2e_instance_info):    
                        # case1:                                            
                        #     sched               |-----| 
                        #     inst    |-----|
                        if instance_info['start'] < sched_info['StartTime'] and instance_info['start'] < sched_info['EndTime'] \
                            and instance_info['end'] < sched_info['StartTime'] and instance_info['end'] < sched_info['EndTime']:
                            continue
                        # case2: 
                        #     sched       |-----|
                        #     inst    |-----|
                        elif instance_info['start'] < sched_info['StartTime'] and instance_info['start'] < sched_info['EndTime'] \
                            and instance_info['end'] >= sched_info['StartTime'] and instance_info['end'] < sched_info['EndTime']:
                            sched_info['Instance'] = instance_info['instance']
                            sched_info['Case'] = 2
                            break
                        # case3:
                        #     sched     |-|
                        #     inst    |-----|
                        elif instance_info['start'] < sched_info['StartTime'] and instance_info['start'] < sched_info['EndTime'] \
                            and instance_info['end'] >= sched_info['StartTime'] and instance_info['end'] >= sched_info['EndTime']:
                            sched_info['Instance'] = instance_info['instance']
                            sched_info['Case'] = 3
                            break
                        # case4:
                        #     sched   |-----|
                        #     inst      |-|
                        elif instance_info['start'] >= sched_info['StartTime'] and instance_info['start'] < sched_info['EndTime'] \
                            and instance_info['end'] >= sched_info['StartTime'] and instance_info['end'] < sched_info['EndTime']:
                            sched_info['Instance'] = instance_info['instance']
                            sched_info['Case'] = 4
                            break
                        # case5:
                        #     sched   |-----|
                        #     inst        |-----|
                        elif instance_info['start'] >= sched_info['StartTime'] and instance_info['start'] < sched_info['EndTime'] \
                            and instance_info['end'] >= sched_info['StartTime'] and instance_info['end'] >= sched_info['EndTime']:
                            sched_info['Instance'] = instance_info['instance']
                            sched_info['Case'] = 5
                            break
                        # case6:  
                        #     sched   |-----|
                        #     inst                |-----|
                        elif instance_info['start'] >= sched_info['StartTime'] and instance_info['start'] >= sched_info['EndTime'] \
                            and instance_info['end'] >= sched_info['StartTime'] and instance_info['end'] >= sched_info['EndTime']:
                            sched_info['Instance'] = -1
                            sched_info['Case'] = 6
                            break
    
    return per_cpu_info

if __name__ == "__main__":
    # matplotlib.use("TkAgg")

    process_name = [
                "republish",
                "op_global_plann",
                "op_trajectory_g",
                "op_trajectory_e",
                "op_behavior_sel",
                "ray_ground_filt",
                "lidar_euclidean",
                "imm_ukf_pda",
                "op_motion_predi",
                "lidar_republish",
                "voxel_grid_filt",
                "ndt_matching",
                "relay",
                "rubis_pose_rela",
                "pure_pursuit",
                "twist_filter",
                "twist_gate"]

    file_path = os.path.dirname(os.path.realpath(__file__))[0:-7]

    # input: Ftrace log - data/sample_autoware_log/sample_autoware_ftrace_log.txt
    file = open(file_path + 'data/sample_autoware_log/sample_autoware_ftrace_log.txt', 'r')

    # input: Dir of Autwoare csv logs - data/sample_autoware_log
    autoware_log_dir = file_path + 'data/sample_autoware_log'

    # input: e2e file - data/sample_autoware_log/system_instance.csv
    autoware_e2e_log_path = file_path + 'data/sample_autoware_log/system_instance.csv'

    per_cpu_info, process_name = parse_ftrace_log(file ,process_name)
    per_cpu_info, max_time = update_per_process_info(per_cpu_info, process_name)
    per_cpu_info = filtering_process_info(per_cpu_info)
    per_cpu_info = add_instance_info(per_cpu_info, autoware_log_dir, autoware_e2e_log_path)

    # output: parsed log path - 'data/sample_autoware_parsed_log.json'
    with open(file_path + '/data/sample_autoware_parsed_log.json', 'w') as json_file:
        json.dump(per_cpu_info, json_file, indent=4)
    
    # output: filtering option file path - '/filtering_option.json'
    filtering_option = create_filtering_option(process_name)
    with open(file_path + '/filtering_option.json', 'w') as json_file:
        json.dump(filtering_option, json_file, indent=4)
