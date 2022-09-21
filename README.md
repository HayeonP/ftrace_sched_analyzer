# ftrace_sched_analyzer

## How to use
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
- (1) Setup configuration on the top of `scripts/sched_analyzer.py`
    - `CPU_NUM`: Number of CPUs in PC that profiles ftrace log
    - `ONLY_AUTOWARE`: If value is true, sched_analyzer parse autoware process only.
- (2) Setup input and output paths in the main of `scripts/sched_analyzer.py`
- (3) Launch script

    ```
    python3 scripts/sched_analyzer.py
    ```
### 4. Visualize data
- (1) Setup configuration on the top of `scripts/log_viz.py`
    - `mode`: Visualization mode. `per_cpu`/ `per_thread`
    - `features`: `skip` / `e2e` / `only_spin`
- (2) Setup input and output paths in the main of `scripts/log_viz.py`
- (3) Launch script

    ```
    python3 scripts/log_viz.py
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
