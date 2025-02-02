from setuptools import config
import json
import numpy as np
from tqdm import tqdm
import pandas as pd
from pandas import json_normalize
import csv
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter, FormatStrFormatter
from matplotlib.patches import Rectangle

import os
import copy


############### TODO ###############
base_path = '/home/hayeonp/git/ftrace_sched_analyzer/data/synthetic_task_log/'
data_dir_name='221114_FIFO_long_chain_spin'

# input
parsed_log_path_ = base_path+data_dir_name+'/synthetic_task.json'
filtering_option_path_ = base_path+data_dir_name+'/filtering_option.json'
e2e_instance_response_time_path_ = base_path+data_dir_name+'/e2e_instance_response_time.json'

# Skip threshold (s)
SKIP_THRESHOLD = 0.000005
# Additional features
#   skip: Skip sched_info that duration is smaller than SKIP_THREASHOLD
#   e2e: Plot e2e box
#   time_range: Target x-axis time range to plot
#   target_instance: Target instance range to plot. Set -1 if you don't want to use
features = ['e2e']
target_cpu = ['cpu6', 'cpu7']
time_range = []
instance_range = {'start':210, 'end':225}

####################################

colors = ['blue', 'green', 'red', 'cyan', 'olive', 'purple', 'darkorange', 'lawngreen', 'slategray']

def mouse_event(event, sched_info_df):
    task = 'none'
    df = sched_info_df.loc[(float(event.xdata) >= sched_info_df['StartTime']) & (float(event.xdata) < sched_info_df['EndTime'])]

    print(task)
    print(df)

def load_data(parsed_log_path, filtering_option_path):
    sched_info_df = pd.DataFrame()
    with open(filtering_option_path) as f:
        config_data = json.load(f)
    with open(parsed_log_path) as f:
        raw_data = json.load(f)
    cores = list(raw_data.keys())
        
    for _, core in enumerate(cores):
        if core not in target_cpu: continue
        sched_data = raw_data[core]
        for name in sched_data:
            if config_data[name]:
                df = json_normalize(sched_data[name])
                if 'StartTime' not in df: continue
                df['Core'] = core
                df['PID'] = df['PID'].astype(int)
                df['Name'] = str(name)
                # df['Label'] = str(name) + ' (' + df['PID'].astype(str) + ')'
                df['Label'] = str(name)
                df['Core'] = str(core)
                df['Duration'] = (df['EndTime'] - df['StartTime']).astype('float64')
                df['StartTime'] = (df['StartTime']).astype('float64')
                df['EndTime'] = (df['EndTime']).astype('float64')
                df['Instance'] = (df['Instance']).astype('int32')
                
                if len(time_range) == 2:
                    df = df.loc[(df['StartTime'] >= time_range[0]) & (df['EndTime'] < time_range[1])]

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

def visualize_per_cpu(sched_info_df, e2e_instance_response_time_path):
    cores = sched_info_df['Core'].unique()
    start_time = float(sched_info_df.min()['StartTime'])
    end_time = float(sched_info_df.max()['EndTime'])

    fig, axis = plt.subplots(len(cores), 1, sharex=True)

    if len(cores) ==  1:
        axis.get_xaxis().set_major_formatter(FormatStrFormatter('%.5f'))
    else:
        for ax in axis:
            ax.get_xaxis().set_major_formatter(FormatStrFormatter('%.5f'))

    with open(e2e_instance_response_time_path) as f:
        e2e_instance_respnose_time_info = json.load(f)


    if instance_range['start'] != -1 or instance_range['end'] != -1:
        if str(instance_range['start']) not in e2e_instance_respnose_time_info or str(instance_range['end']) not in e2e_instance_respnose_time_info: 
            print('Target instance '+str(instance_range)+' does not exist')
            exit()
        start_time = e2e_instance_respnose_time_info[str(instance_range['start'])]['start']
        end_time = e2e_instance_respnose_time_info[str(instance_range['end'])]['end']    

    e2e_info_list = []
    if 'e2e' in features:
        for instance in e2e_instance_respnose_time_info:
            if instance_range['start'] != -1 and instance_range['end'] != -1:
                if int(instance) < instance_range['start'] or int(instance) > instance_range['end']: continue
                if float(e2e_instance_respnose_time_info[instance]['start']) < start_time or float(e2e_instance_respnose_time_info[instance]['start']) > end_time: continue
            e2e_info_list.append({  'Instance': int(instance), 
                                    'StartTime': float(e2e_instance_respnose_time_info[instance]['start']), 
                                    'EndTime': float(e2e_instance_respnose_time_info[instance]['end']), 
                                    'Duration': float(e2e_instance_respnose_time_info[instance]['end']) - float(e2e_instance_respnose_time_info[instance]['start'])
                                })

    for plot_index, core in enumerate(cores):
        per_core_df = sched_info_df.loc[sched_info_df['Core'] == core]
        per_core_df = per_core_df.loc[(per_core_df['StartTime'] >= start_time) & (per_core_df['EndTime'] <= end_time)]

        tasks = per_core_df['Label'].unique()
        tasks = np.append(tasks, 'Total')

        yticks = range(len(tasks))
        yticks = [v*10+5 for v in yticks]

        if len(cores) > 1:
            axis[plot_index].set_yticks(yticks)
            axis[plot_index].set_yticklabels(tasks)
            if len(time_range) == 2:
                axis[plot_index].set_xlim(time_range)
        else:
            axis.set_yticks(yticks)
            axis.set_yticklabels(tasks)
            if len(time_range) == 2:
                axis.set_xlim(time_range)

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

        if len(cores) == 1:
            axis.broken_barh(core_bar_info, (yticks[-1], 10), facecolor='k')
        else:
            axis[plot_index].broken_barh(core_bar_info, (yticks[-1], 10), facecolor='k')
        
        instance_plot_value = []
        for i in [1, 3, 5, 7]:
            if len(yticks) >= i: instance_plot_value.append([(i - 1) * 20, yticks[i * -1]+10])

        if 'e2e' in features:
            for e2e_info in e2e_info_list:
                if len(cores) > 1:
                    axis[plot_index].add_patch(Rectangle((e2e_info['StartTime'], instance_plot_value[e2e_info['Instance'] % len(instance_plot_value)][0]), e2e_info['Duration'], instance_plot_value[e2e_info['Instance'] % len(instance_plot_value)][1], edgecolor=colors[e2e_info['Instance']%len(colors)], facecolor='none'))
                else:
                    axis.add_patch(Rectangle((e2e_info['StartTime'],0), e2e_info['Duration'], yticks[-1]+10, edgecolor=colors[e2e_info['Instance']%len(colors)], facecolor='none'))
        
    # if instance_range['start'] != -1 or instance_range['end'] != -1:
    #     if str(instance_range['start']) not in e2e_instance_respnose_time_info or str(instance_range['end']) not in e2e_instance_respnose_time_info: 
    #         print('Target instance '+str(target_instance)+' does not exist')
    #         exit()
    #     x_start = e2e_instance_respnose_time_info[str(instance_range['start'])]['start']
    #     x_end = e2e_instance_respnose_time_info[str(instance_range['end'])]['end']
    #     plt.xlim(x_start, x_end)

    fig.canvas.mpl_connect('button_press_event', lambda event: mouse_event(event, sched_info_df))
    plt.show()


if __name__ == '__main__':
    sched_info_df = load_data(parsed_log_path_, filtering_option_path_)

    visualize_per_cpu(sched_info_df, e2e_instance_response_time_path_)
    