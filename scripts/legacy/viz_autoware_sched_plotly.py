import argparse
from distutils.command.config import config
import os
import json
import sched
import plotly.graph_objects as go
import numpy as np
import math
from tqdm import tqdm
from plotly.subplots import make_subplots
import plotly as py
import plotly.express as px
import pandas as pd
from pandas.io.json import json_normalize
import csv

############### TODO ###############
# visualization mode ("per_thread" or "per_cpu")
mode = 'per_cpu'
# Skip threshold (s)
SKIP_THRESHOLD = 0.000005

# Additional features
#   skip: Skip sched_info that duration is smaller than SKIP_THREASHOLD
#   e2e: Shoe e2e instasnce range
#   only_spin: Remove all ros thread which don't spin
features = ['e2e', 'only_spin']
target_cpu = ['cpu6', 'cpu7']
####################################

def load_data(data_path, config_path, time_range):
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
                df = json_normalize(sched_data[name])
                if 'StartTime' not in df: continue
                df['Core'] = core
                df['PID'] = df['PID'].astype(int)
                df['Name'] = str(name)
                df['Label'] = str(name) + ' (' + df['PID'].astype(str) + ')'
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

def visualize_per_thread(sched_info_df, e2e_response_time_path='None', e2e_instance_range=[0,0], plot_height=400, time_range=[]):
    config = dict({'scrollZoom': True})

    for core, core_df in tqdm(sched_info_df.groupby('Core')):
        fig = px.bar(core_df, base='StartTime', x='Duration', y='Label', color='Label', hover_data=['Instance'], height=plot_height)
        
        if len(time_range) != 0: fig.update_xaxes(range=time_range)

        if 'skip' in features:
            title=core+' scheduling (Skip threshold: '+str(SKIP_THRESHOLD*1000)+'ms)'
        else:
            title=core+' scheduling'
            
        if 'e2e' in features:
            draw_e2e_instance(fig, e2e_response_time_path, e2e_instance_range)

        fig.update_layout(
            title=title,
            xaxis_title="time (s)",
            barmode='stack',
            font=dict(
                family="Courier New, monospace",
                size=8,
                color="#7f7f7f"
            )
        )
        fig.show()
        
    return

def visualize_per_cpu(sched_info_df, e2e_response_time_path='None', e2e_instance_range=[0,0], plot_height=400, time_range=[]):
    config = dict({'scrollZoom': True})
    
    fig = px.bar(sched_info_df, base='StartTime', x='Duration', y='Core', color='Label', text='Label', hover_data=['EndTime', 'Instance'], height=plot_height)

    if len(time_range) != 0: fig.update_xaxes(range=time_range)

    if 'skip' in features:
        title='Scheduling (Skip threshold: '+str(SKIP_THRESHOLD*1000)+'ms)'
    else:
        title='Scheduling'
    
    if 'e2e' in features:
        draw_e2e_instance(fig, e2e_response_time_path, e2e_instance_range)

    fig.update_layout(
        title=title,
        xaxis_title="time (s)",
        barmode='stack',
        font=dict(
            family="Courier New, monospace",
            color="#7f7f7f"
        )
    )
            
    fig.show()
    
def visualize_per_instance(sched_info_df, e2e_response_time_path='None', e2e_instance_range=[0,0], plot_height=400, time_range=[]):
    config = dict({'scrollZoom': True})
    
    sched_info_df = sched_info_df[sched_info_df['Instance'] != -1]
    fig = px.bar(sched_info_df, base='StartTime', x='Duration', y='Core', color='Instance', text='Label', hover_data=['EndTime', 'Instance'], height=plot_height)

    if len(time_range) != 0: fig.update_xaxes(range=time_range)

    if 'skip' in features:
        title='Scheduling per instance (Skip threshold: '+str(SKIP_THRESHOLD*1000)+'ms)'
    else:
        title='Scheduling per instance'
        
    if 'e2e' in features:
        draw_e2e_instance(fig, e2e_response_time_path, e2e_instance_range)
    
    fig.update_layout(
        title=title,
        xaxis_title="time (s)",
        barmode='stack',
        font=dict(
            family="Courier New, monospace",
            color="#7f7f7f"
        )
    )
            
    fig.show()

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
    
    # data_path = os.path.dirname(os.path.realpath(__file__))[0:-7] + "/data/ftrace_parse_data.json"

    # input: filtering option
    config_path = os.path.dirname(os.path.realpath(__file__))[0:-7] + "/filtering_option.json"
    
    # input: e2e log. Use Autowar Analyzer
    # e2e_response_time_path = os.path.dirname(os.path.realpath(__file__))[0:-7] + 'data/sample_autoware_log/system_instance.csv'
    e2e_response_time_path = '/home/hypark/git/Autoware_Analyzer/files/response_time/system_instance.csv'    

    # input: plot height, e2e_instance_range, time_range
    plot_height = 500
    e2e_instance_range = [980, 990]
    time_range = [9362, 9363]

    sched_info_df = load_data(data_path, config_path, time_range)
    if mode == 'per_thread':
        visualize_per_thread(sched_info_df, e2e_response_time_path=e2e_response_time_path, e2e_instance_range=e2e_instance_range, plot_height=plot_height, time_range=time_range)
    elif mode == 'per_cpu':
        visualize_per_cpu(sched_info_df, e2e_response_time_path=e2e_response_time_path, e2e_instance_range=e2e_instance_range, plot_height=plot_height, time_range=time_range)
    elif mode == 'per_instance':
        visualize_per_instance(sched_info_df, e2e_response_time_path=e2e_response_time_path, e2e_instance_range=e2e_instance_range, plot_height=plot_height, time_range=time_range)

    