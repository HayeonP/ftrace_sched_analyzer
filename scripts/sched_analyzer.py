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
import collections

############### TODO ###############

base_path_ = '/home/hayeonp/git/ftrace_sched_analyzer/data/synthetic_task_log/'
data_dir_name='221027_CFS_chain_Hrate'

# Input
input_ftrace_log_path_ = base_path_+data_dir_name+'/ftrace_log.txt'
pid_name_info_path_ = base_path_+data_dir_name+'/pid_info.json'
start_process_name_ = 'test1'
end_process_name_ = 'test4'

# Output
parsed_log_path_ = base_path_+data_dir_name+'/synthetic_task.json'
filtering_option_path_ = base_path_+'../../filtering_option.json'
e2e_instance_response_time_path_ = base_path_+data_dir_name+'/e2e_instance_response_time.json'

# core number of your computer
CPU_NUM = 8
# analyze target process only
ONLY_TARGETS = False
target_process_name_ = ['test1','test2','test3','test4']
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

    pid_of_instance_processes ={}
    for name in pid_name_map_info:
        pid_of_instance_processes[name] = min(pid_name_map_info[name])

    func_pattern = compile("{}[{}] {} {}: {}: {}")
    sched_switch_pattern = compile("{}[{}] {} {}: {}: prev_comm={} prev_pid={} prev_prio={} prev_state={} ==> next_comm={} next_pid={} next_prio={}")
    update_sched_instance_pattern = compile('{}[{}] {} {}: {}: target_comm={}[{}] sched_instance={}')
    debug_finish_job_pattern = compile('{}-{}[{}] {} {}: {}: instance={}')

    per_cpu_sched_switch_info = {}
    per_pid_instnace_info = {}
    per_pid_job_finish_info = {}

    for i in range(CPU_NUM):
        per_cpu_sched_switch_info['cpu'+str(i)] = []

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

                per_cpu_sched_switch_info['cpu' + str(cpu)].append((time, prev_comm, prev_pid, prev_prio, prev_state, next_comm, next_pid, next_prio))

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

            elif event == 'debug_finish_job':
                debug_finish_job_result = debug_finish_job_pattern.parse(line)
                cpu = int(debug_finish_job_result[2])
                pid = int (debug_finish_job_result[1])
                time = float(debug_finish_job_result[4])
                comm = str(debug_finish_job_result[0])
                instance = int(debug_finish_job_result[6])
                
                if str(pid) not in per_pid_job_finish_info: per_pid_job_finish_info[str(pid)] = {}
                per_pid_job_finish_info[str(pid)][str(instance)] = {'time': time}

    return per_cpu_sched_switch_info, per_pid_instnace_info, per_pid_job_finish_info, process_name, pid_of_instance_processes

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

def update_per_cpu_info(per_cpu_sched_switch_info, per_pid_instnace_info, process_name):
    global count_
    
    per_cpu_info = {}
    per_pid_start_info = {}

    per_pid_cur_instnace = {}
    for key in per_pid_instnace_info:
        per_pid_cur_instnace[key] = {
                                        'idx': 0,  
                                        'time': float(per_pid_instnace_info[key][0]['time']), 
                                        'next_time': float(per_pid_instnace_info[key][1]['time']),
                                        'sched_instance': per_pid_instnace_info[key][0]['sched_instance']
                                    }

    # Init per_process_start_info
    for cpu_idx in range(CPU_NUM):
        cpu = 'cpu'+str(cpu_idx)

        per_cpu_info[cpu] = {}
        per_cpu_sched_switch_info[cpu] = sorted(per_cpu_sched_switch_info[cpu], key = lambda item: item[0], reverse=False)

        per_pid_start_info[cpu] = {}

        for sched_switch_info in per_cpu_sched_switch_info[cpu]:
            time = sched_switch_info[TIME]
            prev_comm = sched_switch_info[PREV_COMM]
            prev_pid =  sched_switch_info[PREV_PID]
            next_comm = sched_switch_info[NEXT_COMM]
            next_pid =  sched_switch_info[NEXT_PID]

            if next_pid not in per_pid_start_info[cpu]: per_pid_start_info[cpu][next_pid] = {'is_start': False, 'start': 0.0, 'name':  next_comm}            

            if per_pid_start_info[cpu][next_pid]['is_start'] == False:
                per_pid_start_info[cpu][next_pid]['is_start'] = True
                per_pid_start_info[cpu][next_pid]['start'] = float(time)
            
            if prev_pid not in per_pid_start_info[cpu]: continue

            if per_pid_start_info[cpu][prev_pid]['is_start'] == True:
                per_pid_start_info[cpu][prev_pid]['is_start'] = False
                target_pid = int(prev_pid)
                target_process = str(prev_comm)                
                target_start_time = float(per_pid_start_info[cpu][prev_pid]['start'])
                target_end_time = float(time)

                if target_process not in process_name: continue
                if target_process not in per_cpu_info[cpu]: per_cpu_info[cpu][target_process] = []

                process_info = {}
                process_info['Count'] = count_
                process_info['PID'] = target_pid
                process_info['StartTime'] = target_start_time
                process_info['EndTime'] = target_end_time
                

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

                per_cpu_info[cpu][target_process].append(process_info)
                count_ = count_ + 1

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

def get_e2e_instance_response_time(per_cpu_info, per_pid_job_finish_info, start_process, end_process, pid_of_instance_processes):
    e2e_instance_response_time = {}

    start_task_pid = pid_of_instance_processes[start_process]
    end_task_pid = pid_of_instance_processes[end_process]

    # Initialize job finish time
    for instance in per_pid_job_finish_info[end_task_pid]:
        end_time = per_pid_job_finish_info[end_task_pid][instance]['time']
        e2e_instance_response_time[instance] = {'start': -100.0, 'end': float(end_time)}

    for cpu in per_cpu_info:
        for process in per_cpu_info[cpu]:
            for info in per_cpu_info[cpu][process]:
                if int(info['Instance']) < 0: continue
                instance = str(info['Instance'])
                pid = str(info['PID'])
                if process == start_process and pid == pid_of_instance_processes[start_process]:
                    if instance not in e2e_instance_response_time: continue                        

                    if  e2e_instance_response_time[instance]['start'] < 0 or e2e_instance_response_time[instance]['start'] > info['StartTime']:
                        e2e_instance_response_time[instance]['start'] = info['StartTime']
                        continue

    remove_targets = []
    for instance in e2e_instance_response_time:
        if float(e2e_instance_response_time[instance]['start']) < 0 or float(e2e_instance_response_time[instance]['end']) < 0:
            remove_targets.append(instance)

    for target in remove_targets:
        e2e_instance_response_time.pop(target)

    return e2e_instance_response_time

def analyze_e2e_instance_response_time(e2e_instance_response_time):
    maximum = 0
    max_instance = 0
    avg = 0
    instnace_leakages = []

    prev_instance = -1
    for instance in e2e_instance_response_time:    
        if float(e2e_instance_response_time[instance]['start']) < 0 or  float(e2e_instance_response_time[instance]['end']) < 0: continue
        cur_reseponse_time = float(e2e_instance_response_time[instance]['end']) - float(e2e_instance_response_time[instance]['start'])
        if maximum < cur_reseponse_time:
            maximum = cur_reseponse_time
            max_instance = instance
        avg = cur_reseponse_time + avg

        cur_instance = int(instance)
        if prev_instance == -1:
            prev_instance = cur_instance
            continue

        if prev_instance + 1 != cur_instance:
            for i in range(prev_instance + 1, cur_instance): instnace_leakages.append(i)
        prev_instance = cur_instance            

    avg = avg / len(e2e_instance_response_time)

    e2e_instance_analysis_result = {'max_e2e_response_time': maximum, 'avg_e2e_response_time': avg, 'max_instance': max_instance, 'instance_leakges': instnace_leakages}    

    with open(base_path_+data_dir_name+'/e2e_instance_analysis_result.json', 'w') as json_file:
        json.dump(e2e_instance_analysis_result, json_file, indent=4)

    return maximum, max_instance, avg

def sort_per_cpu_info(per_cpu_info):
    for cpu in per_cpu_info:
        per_cpu_info[cpu] = collections.OrderedDict(sorted(per_cpu_info[cpu].items(), reverse=True))

    return per_cpu_info



if __name__ == "__main__":
    file_path = os.path.dirname(os.path.realpath(__file__))[0:-7]

    file = open(input_ftrace_log_path_, 'r')

    per_cpu_sched_switch_info, per_pid_instnace_info, per_pid_job_finish_info, process_name, pid_of_instance_processes = parse_ftrace_log(file ,target_process_name_, pid_name_info_path_)
    per_cpu_info = update_per_cpu_info(per_cpu_sched_switch_info, per_pid_instnace_info, process_name)
    per_cpu_info = sort_per_cpu_info(per_cpu_info)


    with open(parsed_log_path_, 'w') as json_file:
        json.dump(per_cpu_info, json_file, indent=4)

    filtering_option = create_filtering_option(process_name)
    with open(filtering_option_path_, 'w') as json_file:
        json.dump(filtering_option, json_file, indent=4)

    e2e_instance_response_time = get_e2e_instance_response_time(per_cpu_info, per_pid_job_finish_info, start_process_name_, end_process_name_, pid_of_instance_processes)
    max_e2e, max_instance, avg_e2e = analyze_e2e_instance_response_time(e2e_instance_response_time)

    with open(e2e_instance_response_time_path_, 'w') as json_file:
        json.dump(e2e_instance_response_time, json_file, indent=4)