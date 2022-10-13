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

# Input
input_ftrace_log_path_ = '/home/hayeonp/git/ftrace_sched_analyzer/data/synthetic_task_log/221013_ftrace_log.txt'
pid_name_info_path_ = '/home/hayeonp/git/ftrace_sched_analyzer/data/synthetic_task_log/221013_pid_info.json'
start_process_response_time_path_ = '/home/hayeonp/git/ftrace_sched_analyzer/data/synthetic_task_log/221013-2_test1.csv'
end_process_response_time_path_ = '/home/hayeonp/git/ftrace_sched_analyzer/data/synthetic_task_log/221013-2_test4.csv'

# Output
parsed_log_path_ = '/home/hayeonp/git/ftrace_sched_analyzer/data/221013_synthetic_task.json'
filtering_option_path_ = '/home/hayeonp/git/ftrace_sched_analyzer/filtering_option.json'
e2e_instance_response_time_path_ = '/home/hayeonp/git/ftrace_sched_analyzer/data/synthetic_task_log/221013-2_e2e_instance_response_time.json'

# core number of your computer
CPU_NUM = 8
# analyze target process only
ONLY_TARGETS = False
target_process_name_ = ['test1','test2','test3']
# time range
time_range_ = []

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
NONE = -100.0

def map_pid_to_process_name(process_name, pid, pid_name_info):    
    for pid_mapped_process_name in pid_name_info:
        if str(pid) in pid_name_info[pid_mapped_process_name]:
            return pid_mapped_process_name

    return process_name

#
count_ = 0
def parse_ftrace_log(file, process_name, pid_name_info_path):    
    try:
        pid_name_map_info = json.load(open(pid_name_info_path, 'r'))   
    except:
        pid_name_map_info = {}

    func_pattern = compile("{}[{}] {} {}: {}: {}")
    sched_switch_pattern = compile("{}[{}] {} {}: {}: prev_comm={} prev_pid={} prev_prio={} prev_state={} ==> next_comm={} next_pid={} next_prio={}")
    update_sched_instance_pattern = compile('{}[{}] {} {}: {}: target_comm={}[{}] sched_instance={}')

    per_cpu_info = {}
    per_pid_instnace_info = {}
    
    for i in range(CPU_NUM):
        per_cpu_info['cpu'+str(i)] = []

    if not ONLY_TARGETS:
        process_name = []

    while True:
        line = file.readline()

        if not line:
            break
        
        result = func_pattern.parse(line)
        
        if result != None:
            event = result[4]
            if event == 'sched_switch':
                sched_switch_parse_result = sched_switch_pattern.parse(line)
                cpu = int(sched_switch_parse_result[1])
                time = float(sched_switch_parse_result[3])
                prev_comm = sched_switch_parse_result[5]
                prev_pid = int(sched_switch_parse_result[6])
                prev_prio = int(sched_switch_parse_result[7])
                prev_state = sched_switch_parse_result[8]
                next_comm = sched_switch_parse_result[9]
                next_pid = int(sched_switch_parse_result[10])
                next_prio = int(sched_switch_parse_result[11])

                prev_comm = map_pid_to_process_name(prev_comm, prev_pid, pid_name_map_info)
                next_comm = map_pid_to_process_name(next_comm, next_pid, pid_name_map_info)

                per_cpu_info['cpu' + str(cpu)].append((time, prev_comm, prev_pid, prev_prio, prev_state, next_comm, next_pid, next_prio))

                if not ONLY_TARGETS:
                    already_exist = False
                    for i in range(len(process_name)):
                        if process_name[i] == prev_comm:
                            already_exist = True
                    if not already_exist:
                        if not prev_comm[0:7] == "swapper":
                            process_name.append(prev_comm)
            elif event == 'update_sched_instance':
                update_sched_instance_parse_result = update_sched_instance_pattern.parse(line)
                cpu = int(update_sched_instance_parse_result[1])
                time = float(update_sched_instance_parse_result[3])
                target_comm=str(update_sched_instance_parse_result[5])
                target_pid=int(update_sched_instance_parse_result[6])
                sched_instance=int(update_sched_instance_parse_result[7])
                if str(target_pid) not in per_pid_instnace_info: per_pid_instnace_info[str(target_pid)] = []
                per_pid_instnace_info[str(target_pid)].append({'time': time, 'sched_instance': sched_instance})

    return per_cpu_info, per_pid_instnace_info, process_name

def update_per_pid_cur_instance(cur_instance, instance_info):
    idx = cur_instance['idx']
    if idx + 1 <= len(instance_info) - 1:
        cur_instance['idx'] = idx + 1
        cur_instance['time'] = float(instance_info[idx]['time'])
        cur_instance['next_time'] = float(instance_info[idx+1]['time'])
        cur_instance['sched_instance']= instance_info[idx]['sched_instance']
    elif idx + 1 > len(instance_info) - 1: # No next enry in instance_info
        cur_instance['idx'] = idx
        cur_instance['time'] = float(instance_info[idx]['time'])
        cur_instance['next_time'] = NONE
        cur_instance['sched_instance']= NONE
    return cur_instance

def update_per_process_info(cpu_info, per_pid_instnace_info, process_name):
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

    per_pid_cur_instnace = {}
    for key in per_pid_instnace_info:
        per_pid_cur_instnace[key] = {'idx': 0, 'time': float(per_pid_instnace_info[key][0]['time']), 'next_time': float(per_pid_instnace_info[key][1]['time']),'sched_instance': per_pid_instnace_info[key][0]['sched_instance']}

    
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
                            process_info['PID'] = int(per_cpu_start_info['cpu'+str(i)][process_name[k]][2])
                            process_info['StartTime'] = float(per_cpu_start_info['cpu'+str(i)][process_name[k]][1])
                            process_info['EndTime'] = float(cpu_info['cpu'+str(i)][j][TIME])

                            
                            # Set sched instance info
                            while(True):
                                if str(process_info['PID']) not in per_pid_cur_instnace or per_pid_cur_instnace[str(process_info['PID'])]['sched_instance'] == NONE:
                                    process_info['Instance'] = NONE
                                    break
                                elif process_info['EndTime'] <= per_pid_cur_instnace[str(process_info['PID'])]['next_time']: 
                                    process_info['Instance'] = per_pid_cur_instnace[str(process_info['PID'])]['sched_instance']
                                    break
                                elif process_info['EndTime'] > per_pid_cur_instnace[str(process_info['PID'])]['next_time']: 
                                    per_pid_cur_instnace[process_info['PID']] = update_per_pid_cur_instance(per_pid_cur_instnace[str(process_info['PID'])], per_pid_instnace_info[str(process_info['PID'])])
                                    process_info['Instance'] = per_pid_cur_instnace[str(process_info['PID'])]['sched_instance']                                  

                            if len(time_range_) == 2: 
                                if process_info['StartTime'] < time_range_[0] or process_info['EndTime'] > time_range_[1]: break                            

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
                node_instance_info.append({'Instance':instance, 'StartTime':float(start), 'EndTime':float(end)})
                instance = NONE
        
        prev_instance = line[4]
    
    return pid, node_instance_info
    
def get_e2e_instance_response_time(start_path, end_path):
    start_file = open(start_path, 'r')
    end_file = open(end_path, 'r')
    start_reader = csv.reader(start_file)
    end_reader = csv.reader(end_file)

    e2e_instance_response_time = {}
    for line in end_reader:
        if 'instance' in line: continue
        pid = int(line[0])
        start = float(line[1])
        end = float(line[2])
        instance = int(line[3])
        if str(instance) not in e2e_instance_response_time:
            e2e_instance_response_time[str(instance)] = {'start': -1, 'end': end}
            continue
        if float(e2e_instance_response_time[str(instance)]['end']) > end:
            e2e_instance_response_time[str(instance)]['end'] = end
    
    for line in start_reader:
        if 'instance' in line: continue
        pid = line[0]
        start = line[1]
        end = line[2]
        instance = line[3]
        if str(instance) not in e2e_instance_response_time: continue
        if e2e_instance_response_time[str(instance)]['start'] < 0: e2e_instance_response_time[str(instance)]['start'] = start # NONE
        elif e2e_instance_response_time[str(instance)]['start'] > start: e2e_instance_response_time[str(instance)]['start'] = start

    remove_target_instnace = []
    for instance in e2e_instance_response_time:
        if e2e_instance_response_time[str(instance)]['start'] == NONE: remove_target_instnace.append(instance)
    for target in remove_target_instnace:
        e2e_instance_response_time.pop(target, 0)

    return e2e_instance_response_time

if __name__ == "__main__":
    file_path = os.path.dirname(os.path.realpath(__file__))[0:-7]

    file = open(input_ftrace_log_path_, 'r')

    per_cpu_info, per_pid_instnace_info, process_name = parse_ftrace_log(file ,target_process_name_, pid_name_info_path_)
    per_cpu_info, max_time = update_per_process_info(per_cpu_info, per_pid_instnace_info, process_name)
    per_cpu_info = filtering_process_info(per_cpu_info)    
    
    with open(parsed_log_path_, 'w') as json_file:
        json.dump(per_cpu_info, json_file, indent=4)
    
    filtering_option = create_filtering_option(process_name)
    with open(filtering_option_path_, 'w') as json_file:
        json.dump(filtering_option, json_file, indent=4)

    e2e_instance_response_time = get_e2e_instance_response_time(start_process_response_time_path_, end_process_response_time_path_)
    with open(e2e_instance_response_time_path_, 'w') as json_file:
        json.dump(e2e_instance_response_time, json_file, indent=4)