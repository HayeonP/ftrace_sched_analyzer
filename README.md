# ftrace_sched_analyzer

## How to use
### 1. Prepare ftrace log and PID name info
```
cd ftrace

# Start ftrace.
sudo sh ./set_ftrace.sh

# Finish ftrace. It creates output log ftrace_log.txt.
sudo sh ./get_ftrace.sh

# If you need to use custom process name for some pids, prepare PID name info based on following format.
{
    "test1": [ # Custom process name
        "16833", # Corresponding pid1
        "16840", # Corresponding pid2
        "16841", # Corresponding pid3
        "16842", # Corresponding pid4
        "16857"  # Corresponding pid5
    ]
}
```
- If you need to save larger trace information, change variable `BUFFER_SIZE` in `set_ftrace.sh`.
- For instance profiling, you need to setup relative system calls.

### 2. Analyze ftrace log
- (1) Setup configuration on the top of `scripts/sched_analyzer.py`
    - `input_ftrace_log_path_`: File path of ftrace log
    - `pid_name_info_path_`: File path of PID name info(Not necessary)
    - `parsed_log_path_`: File path to write result
    - `filtering_output_`: File path to write filtering option
    - `CPU_NUM`: Number of CPUs in PC that profiles ftrace log
    - `ONLY_TARGETS`: If value is true, sched_analyzer target process only. Target processes shoubld be described to list `target_process_name`.
    - `time_range` : Target time range(Not necessary)
- (2) Launch script

    ```
    cd scripts
    python3 sched_analyzer.py
    ```
### 3. Visualize data
- (1) Setup configuration on the top of `scripts/viz_sched_pyplot.py`
    - `parsed_log_path_`: File path of result from `sched_analyzer.py`
    - `filtering_option_path_`: File path of filtering option
    - `features`: `skip` 
    - `time_range` : Target time range(Not necessary)
- (2) Launch script

    ```
    cd scripts
    python3 viz_sched_pyplot.py
    ```


## json file format
- (PID, Start Time, End Time)
    ```
    .json
    └───cpu0
    │   │   op_global_plann
    │   │   op_trajectory_g
    │   │   ...
    │   │   twist_gate
    │   
    └───cpu1
    │   │   op_global_plann
    │   │   op_trajectory_g
    │   │   ...
    │   │   twist_gate
    │   ...
    └───cpu11
    │   │   op_global_plann
    │   │   op_trajectory_g
    │   │   ...
    │   │   twist_gate
    ```

---

## How to use(Deprecated, for `sched_analyzer_autoware.py` and `viz_autoware_sched_pyplot.py`)
### 1. Get ftrace log
```
cd ftrace

# Start ftrace.
sudo sh ./set_ftrace.sh

# Finish ftrace. It creates output log ftrace_log.txt.
sudo sh ./get_ftrace.sh
```
- If you need to save larger trace information, change variable `BUFFER_SIZE` in `set_ftrace.sh`.

### 2. Prepare Autoware log
- (1) Profiling log for each node
- (2) E2E profiling log ( Ref: https://github.com/HayeonP/Autoware_Analyzer)

### 3. Parse log
- (1) Setup configuration on the top of `scripts/sched_analyzer_autoware.py`
    - `CPU_NUM`: Number of CPUs in PC that profiles ftrace log
    - `ONLY_AUTOWARE`: If value is true, sched_analyzer parse autoware process only.
- (2) Setup input and output paths in the main of `scripts/sched_analyzer_autoware.py`
- (3) Launch script

    ```
    python3 scripts/sched_analyzer.py
    ```
### 4. Visualize data
- (1) Setup configuration on the top of `scripts/viz_autoware_sched_pyplot.py`
    - `mode`: Visualization mode. `per_cpu`/ `per_thread`
    - `features`: `skip` / `e2e` / `only_spin`
- (2) Setup input and output paths in the main of `scripts/viz_autoware_sched_pyplot.py`
- (3) Launch script

    ```
    python3 scripts/log_viz.py
    ```