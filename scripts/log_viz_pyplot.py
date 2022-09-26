from distutils.command.config import config
import json
import plotly.graph_objects as go
import numpy as np
from tqdm import tqdm
import pandas as pd
import csv
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

import os
import copy


############### TODO ###############
# visualization mode ('per_cpu' and 'per_instance')
mode = 'per_cpu'
# Skip threshold (s)
SKIP_THRESHOLD = 0.000005

# Additional features
#   skip: Skip sched_info that duration is smaller than SKIP_THREASHOLD
#   only_spin: Remove all ros thread which don't spin
features = ['e2e']
target_cpu = ['cpu6', 'cpu7']
####################################

colors = ['blue', 'green', 'red', 'cyan', 'olive', 'purple', 'darkorange', 'lawngreen', 'slategray']

def mouse_event(event, sched_info_df):
    task = 'none'
    df = sched_info_df.loc[(float(event.xdata) >= sched_info_df['StartTime']) & (float(event.xdata) < sched_info_df['EndTime'])]

    print(task)
    print(df)

def load_data(data_path, config_path):
    sched_info_df = pd.DataFrame()
    with open(config_path) as f:
        config_data = json.load(f)
    with open(data_path) as f:
        raw_data = json.load(f)
    cores = list(raw_data.keys())
        
    for _, core in enumerate(cores):
        if core not in target_cpu: continue
        sched_data = raw_data[core]
        for name in sched_data:
            if config_data[name]:
                df = pd.json_normalize(sched_data[name])
                if 'StartTime' not in df: continue
                df['Core'] = core
                df['PID'] = df['PID'].astype(int)
                df['Name'] = str(name)
                # df['Label'] = str(name) + ' (' + df['PID'].astype(str) + ')'
                df['Label'] = str(name)
                df['Core'] = str(core)
                df['Duration'] = df['EndTime'] - df['StartTime']                
                df['StartTime'] = df['StartTime']
                df['Instance'] = df['Instance']                                
                
                if 'skip' in features:
                    df = df[df.Duration >= SKIP_THRESHOLD]
                if df.size == 0: continue
                
                if sched_info_df.size == 0:
                    sched_info_df = df
                else:                    
                    sched_info_df = pd.concat([sched_info_df,df])

    if 'only_spin' in features:
        remove_target_pids=[]
        for name, name_df in sched_info_df.groupby('Name'):
            if name_df['PID'].unique().size <= 1: continue
            pids = list(name_df['PID'].unique())
            pids.sort()
            for pid in pids[1:]: remove_target_pids.append(pid)

        for pid in remove_target_pids:
            sched_info_df = sched_info_df[sched_info_df['PID'] != pid]
            
            

    
    return sched_info_df

def get_facecolor(task_df):
    facecolor=[]
    for i, instance in enumerate(task_df['Instance']):
        if instance < 0: facecolor.append('k')
        else: facecolor.append(colors[int(instance)%len(colors)])

    return facecolor

def visualize_per_cpu(sched_info_df, e2e_response_time_path):    
    cores = sched_info_df['Core'].unique()

    fig, axis = plt.subplots(len(cores), 1, sharex=True)    

    e2e_info_list = []
    with open(e2e_response_time_path) as f:
        reader = csv.reader(f)
        for line in reader:
            if 'instance' in line: continue
            e2e_info_list.append({'Instance': int(line[0]), 'StartTime': float(line[1]), 'EndTime': float(line[2]), 'Duration': float(line[3])})

    for plot_index, core in enumerate(cores):
        per_core_df = sched_info_df.loc[sched_info_df['Core'] == core]
        tasks = per_core_df['Label'].unique()
        tasks = np.append(tasks, 'Total')
        
        yticks = range(len(tasks))
        yticks = [v*10+5 for v in yticks]

        if len(cores) > 1:
            axis[plot_index].set_yticks(yticks)
            axis[plot_index].set_yticklabels(tasks)
        else:
            axis.set_yticks(yticks)
            axis.set_yticklabels(tasks)

        for i, task in enumerate(tasks):
            if 'cpu' in task: continue
            task_df = per_core_df.loc[per_core_df['Label'] == task]

            bar_info = [(task_df['StartTime'].iloc[j], task_df['Duration'].iloc[j]) for j in range(len(task_df))]               
            facecolor = get_facecolor(task_df)

            if len(cores) > 1:
                axis[plot_index].broken_barh(bar_info, (yticks[i], 10),facecolor=facecolor)
            else:
                axis.broken_barh(bar_info, (yticks[i], 10),facecolor=facecolor)

        # Plot core scheduling
        core_bar_info = [(per_core_df['StartTime'].iloc[j], per_core_df['Duration'].iloc[j]) for j in range(len(per_core_df))]
        axis[plot_index].broken_barh(core_bar_info, (yticks[-1], 10), facecolor='k')

        for e2e_info in e2e_info_list:
            if len(cores) > 1:
                axis[plot_index].add_patch(Rectangle((e2e_info['StartTime'],0), e2e_info['Duration'], yticks[-1]+10, edgecolor=colors[e2e_info['Instance']%len(colors)], facecolor='none'))
            else:
                axis.add_patch(Rectangle((e2e_info['StartTime'],0), e2e_info['Duration'], yticks[-1]+10, edgecolor=colors[e2e_info['Instance']%len(colors)], facecolor='none'))
    
    fig.canvas.mpl_connect('button_press_event', lambda event: mouse_event(event, sched_info_df))
    plt.show()

    return

def visualize_per_instance(e2e_fileE_path):
    instance_info_list = []
    with open(e2e_response_time_path) as f:
        reader = csv.reader(f)
        for line in reader:
            if 'instance' in line: continue
            instance_info_list.append({'Instance': line[0], 'StartTime': line[1], 'EndTime': line[2]})
    
    max_overlap = 1
    for instance_idx, instance_info in enumerate(instance_info_list):
        target_idx = instance_idx + 1
        cur_overlap = 1
        
        while(True):
            if target_idx >= len(instance_info_list): break
            if float(instance_info['EndTime']) > float(instance_info_list[target_idx]['StartTime']):
                cur_overlap = cur_overlap + 1
            else: break
            target_idx = target_idx + 1
        
        max_overlap = max(max_overlap, cur_overlap)

    print(max_overlap)
    exit()

    # sched_info_df.sort_values(by=['StartTime'])
    # sched_info_df.sort_values(by=['Instance'])
    
    # instances = sched_info_df['Instance'].unique()
    # cores = sched_info_df['Core'].unique()

    # fig, axis = plt.subplots(len(cores), 1, sharex=True, sharey=True)    

    # max_overlap = 1
    # for plot_index, core in enumerate(cores):
    #     instance_info_list = []
    #     for instance in instances:
    #         instance_df = sched_info_df.loc[(sched_info_df['Instance'] == instance) & (sched_info_df['Core'] == core)]
    #         instance_info_list.append({'Instance': instance, 'StartTime': instance_df['StartTime'].iloc[0] , 'EndTime': instance_df['EndTime'].iloc[-1]})
        
    #     print(instance_info_list)
    #     exit()

    #     # Get max overlap
    #     for i, instance_info in enumerate(instance_info_list):
    #         local_overlap = 1
    #         cur_end_time = instance_info['EndTime']
    #         target_idx = i+1

    #         while(True):                
    #             if target_idx >= len(instance_info_list): break
    #             next_start_time = instance_info_list[target_idx]['StartTime']
    #             if cur_end_time > next_start_time:
    #                 local_overlap = local_overlap+1
    #             target_idx = target_idx + 1
            
    #         # max_overlap = max(max_overlap, local_overlap)
    #         # if(max_overlap == 237): print(instance_info)

    #     print(max_overlap)
    #     print(len(instance_info_list))
    #     exit()
        


    plt.show()
    
def draw_e2e_instance(fig, e2e_response_time_path, e2e_instance_range):
    if e2e_response_time_path == 'None': return
    
    e2e_info = []
    with open(e2e_response_time_path) as f:
        reader = csv.reader(f)
        for line in reader:
            if 'response_time' in line: continue
            e2e_info.append({'Start':float(line[1]), 'End':float(line[2]), 'Instance':int(line[0])})
    
    for e2e in e2e_info:
        if e2e['Instance'] >= e2e_instance_range[0] and e2e['Instance'] < e2e_instance_range[1]:
            fig.add_vrect(x0=e2e['Start'], x1=e2e['End'], annotation_text=e2e['Instance'], annotation_position='top left', fillcolor='green', opacity=0.1, line_width=3)
            
    return

if __name__ == '__main__':
    # input: parsed log
    # data_path = os.path.dirname(os.path.realpath(__file__))[0:-7] + "data/sample_autoware_parsed_log.json"
    data_path = os.path.dirname(os.path.realpath(__file__))[0:-7] + "data/220923_autoware_parsed_log.json"
    
    # input: e2e log. Use Autowar Analyzer
    # e2e_response_time_path = os.path.dirname(os.path.realpath(__file__))[0:-7] + 'data/sample_autoware_log/system_instance.csv'
    e2e_response_time_path = '/home/hypark/git/Autoware_Analyzer/files/response_time/system_instance.csv' 

    # input: filtering option
    config_path = os.path.dirname(os.path.realpath(__file__))[0:-7] + "/filtering_option.json"
    
    sched_info_df = load_data(data_path, config_path)

    if mode == 'per_cpu':
        visualize_per_cpu(sched_info_df, e2e_response_time_path)
    elif mode == 'per_instance':
        visualize_per_instance(e2e_response_time_path) 
    