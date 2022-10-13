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
from threading import Thread
import time
import os
import multiprocessing
from collections import defaultdict

############### TODO ###############
# core number of your computer
CPU_NUM = 8
# analyze autoware node only
ONLY_AUTOWARE = False
# time range
time_range = []
# instance offset
instance_offset = 0.25
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



def get_thread_cnt():
    cur_core_cnt = os.cpu_count()
    thread_cnt = int(cur_core_cnt*0.8)
    return thread_cnt

def file_len(file_path):
    with open(file_path, 'r') as file:
        for i, _ in enumerate(file):
            pass
    return i + 1

def parse_ftrace_log(ftrace_path, process_name):
    file = open(ftrace_path, 'r')
    line_cnt = int(file_len(ftrace_path))

    paralleliation_cnt = int(get_thread_cnt())
    index_per_process = []

    base_index_cnt = int(line_cnt/paralleliation_cnt)    

    for i in range(paralleliation_cnt):
        index_per_process.append({'Start': i * base_index_cnt, 'End': (i+1) * base_index_cnt})

    parallel_processes = []
    for i, target_index in  enumerate(index_per_process):
        data = file.readlines()[target_index['Start']: target_index['End']]       
        p = multiprocessing.Process(target=_parse_ftrace_log, args=(data, process_name))
        parallel_processes.append(p)
        file.seek(0)
    
    for p in parallel_processes:
        p.start()

    for p in parallel_processes:
        p.join()
    
    # Merge results
    per_cpu_info_file_paths = list(filter(lambda f: f.startswith('__') and f.endswith('.json'), os.listdir('.')))
    process_name_file_paths = list(filter(lambda f: f.startswith('__') and f.endswith('.csv'), os.listdir('.')))

    per_cpu_info = {}
    for path in per_cpu_info_file_paths:
        with open(path) as f:
            data = json.load(f)            
            for key in data:
                if key not in per_cpu_info: per_cpu_info[key] = []
            
            per_cpu_info = {key: per_cpu_info[key] + data[key] for key in data}

        os.remove(path)


    process_name = []
    for path in process_name_file_paths:
        with open(path) as f:
            reader=csv.reader(f)
            for _process_name in reader:
                if _process_name not in process_name: process_name.append(_process_name[0])
        os.remove(path)

    return per_cpu_info, process_name

def _parse_ftrace_log(data, process_name):
    func_pattern = compile("{}[{}] {} {}: {}: {}")
    sched_switch_pattern = compile("{}[{}] {} {}: {}: prev_comm={} prev_pid={} prev_prio={} prev_state={} ==> next_comm={} next_pid={} next_prio={}")

    per_cpu_info = {}
    
    for i in range(CPU_NUM):
        per_cpu_info['cpu'+str(i)] = []

    if not ONLY_AUTOWARE:
        process_name = []

    for line in data:
        line = line.strip()
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
    
    with open('./__parse_ftrace_log_per_cpu_info_'+str(os.getpid())+'.json', 'w') as json_file:
        json.dump(per_cpu_info, json_file, indent=4)
    
    with open('./__parse_ftrace_log_process_'+str(os.getpid())+'.csv', 'w') as csv_file:
        writer = csv.writer(csv_file)
        for name in process_name: 
            writer.writerow([name])    

def update_per_process_info(cpu_info, process_name):
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
                            process_info['PID'] = per_cpu_start_info['cpu'+str(i)][process_name[k]][2]
                            process_info['StartTime'] = per_cpu_start_info['cpu'+str(i)][process_name[k]][1]
                            process_info['EndTime'] = cpu_info['cpu'+str(i)][j][TIME]
                            process_info['Instance'] = NONE

                            if process_info['StartTime'] < time_range[0] or process_info['EndTime'] > time_range[1]: break

                            per_cpu_info['cpu'+str(i)][process_name[k]].append(process_info)
                
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
                node_instance_info.append({'Instance':instance, 'StartTime':float(start), 'EndTime':float(end)})
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

        e2e_instance_info.append({'Instance':int(instance), 'StartTime':float(start), 'EndTime':float(end)})

    return e2e_instance_info

def add_instance_info(per_cpu_info, autoware_log_dir, autoware_e2e_log_path):

    per_node_instance_info = {}
    node_name_list = []

    # Get node instance info
    for log_path in glob.glob(os.path.join(autoware_log_dir, '*.csv')):
        node_name = log_path.split('/')[-1].split('.')[0]
        node_name_list.append(node_name)

        per_node_instance_info[node_name] = []
        with open(log_path) as f:
            reader = csv.reader(f)
            for line in reader:
                if 'iter' in line: continue                
                if len(line) < 7: break
                per_node_instance_info[node_name].append({'Instance': float(line[4]), 'StartTime': float(line[2]), 'EndTime': float(line[3])})


    for core in per_cpu_info:
        for process_name in per_cpu_info[core]:
            # Get target node instance info
            target_node_instance_info = []
            for node_name in node_name_list:
                if not str_match_from_front(process_name, node_name): continue
                else: target_node_instance_info = per_node_instance_info[node_name]

            # Write instance info
            for sched_info in per_cpu_info[core][process_name]:
                if sched_info['Instance'] != NONE: continue                

                for instance_info in target_node_instance_info:
                    # case1:                                            
                    #     sched               |-----| 
                    #     inst    |-----|
                    if instance_info['StartTime'] - instance_offset < sched_info['StartTime'] and instance_info['StartTime'] - instance_offset < sched_info['EndTime'] \
                        and instance_info['EndTime'] < sched_info['StartTime'] and instance_info['EndTime'] < sched_info['EndTime']:
                        continue
                    # case2: 
                    #     sched       |-----|
                    #     inst    |-----|
                    elif instance_info['StartTime'] - instance_offset < sched_info['StartTime'] and instance_info['StartTime'] - instance_offset < sched_info['EndTime'] \
                        and instance_info['EndTime'] >= sched_info['StartTime'] and instance_info['EndTime'] < sched_info['EndTime']:
                        sched_info['Instance'] = instance_info['Instance']
                        sched_info['Case'] = 2
                        break
                    # case3:
                    #     sched     |-|
                    #     inst    |-----|
                    elif instance_info['StartTime'] - instance_offset < sched_info['StartTime'] and instance_info['StartTime'] - instance_offset < sched_info['EndTime'] \
                        and instance_info['EndTime'] >= sched_info['StartTime'] and instance_info['EndTime'] >= sched_info['EndTime']:
                        sched_info['Instance'] = instance_info['Instance']
                        sched_info['Case'] = 3
                        break
                    # case4:
                    #     sched   |-----|
                    #     inst      |-|
                    elif instance_info['StartTime'] - instance_offset >= sched_info['StartTime'] and instance_info['StartTime'] - instance_offset < sched_info['EndTime'] \
                        and instance_info['EndTime'] >= sched_info['StartTime'] and instance_info['EndTime'] < sched_info['EndTime']:
                        sched_info['Instance'] = instance_info['Instance']
                        sched_info['Case'] = 4
                        break
                    # case5:
                    #     sched   |-----|
                    #     inst        |-----|
                    elif instance_info['StartTime'] - instance_offset >= sched_info['StartTime'] and instance_info['StartTime'] - instance_offset < sched_info['EndTime'] \
                        and instance_info['EndTime'] >= sched_info['StartTime'] and instance_info['EndTime'] >= sched_info['EndTime']:
                        sched_info['Instance'] = instance_info['Instance']
                        sched_info['Case'] = 5
                        break
                    # case6:  
                    #     sched   |-----|
                    #     inst                |-----|
                    elif instance_info['StartTime'] - instance_offset >= sched_info['StartTime'] and instance_info['StartTime'] - instance_offset >= sched_info['EndTime'] \
                        and instance_info['EndTime'] >= sched_info['StartTime'] and instance_info['EndTime'] >= sched_info['EndTime']:
                        sched_info['Instance'] = -1
                        sched_info['Case'] = 6
                        break
                    
    return per_cpu_info

if __name__ == "__main__":
    # matplotlib.use("TkAgg")
    file_path = os.path.dirname(os.path.realpath(__file__))[0:-7]

    autoware_process_name = [
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

    # input: Ftrace log - data/sample_autoware_log/sample_autoware_ftrace_log.txt
    ftrace_path = '/home/hypark/git/ExperimentTools/ftrace_sched_analyzer/ftrace/ftrace_log.txt'

    # input: Dir of Autwoare csv logs - data/sample_autoware_log
    autoware_log_dir = '/home/hypark/git/Autoware_Analyzer/files/response_time'

    # input: e2e file - data/sample_autoware_log/system_instance.csv
    autoware_e2e_log_path = '/home/hypark/git/Autoware_Analyzer/files/response_time/system_instance.csv'

    start = time.time()
    per_cpu_info, process_name = parse_ftrace_log(ftrace_path, autoware_process_name)
    end = time.time()
    print('parse_ftrace_log:', end-start)

    start = time.time()
    per_cpu_info = update_per_process_info(per_cpu_info, process_name)
    end = time.time()
    print('update_per_process_info:', end-start)

    start = time.time()
    per_cpu_info = filtering_process_info(per_cpu_info)
    end = time.time()
    print('filtering_process_info:', end-start)

    start = time.time()
    per_cpu_info = add_instance_info(per_cpu_info, autoware_log_dir, autoware_e2e_log_path)
    end = time.time()
    print('add_instance_info:', end-start)

    start = time.time()
    # output: parsed log path - 'data/sample_autoware_parsed_log.json'
    with open(file_path + '/data/220923_autoware_parsed_log.json', 'w') as json_file:
        json.dump(per_cpu_info, json_file, indent=4)
    end = time.time()
    print('Write json:', end-start)


    # output: filtering option file path - '/filtering_option.json'
    filtering_option = create_filtering_option(process_name)
    with open(file_path + '/filtering_option.json', 'w') as json_file:
        json.dump(filtering_option, json_file, indent=4)
