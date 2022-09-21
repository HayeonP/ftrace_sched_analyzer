#!/bin/bash

BUFFER_SIZE=1408 # Size of ftrace log buffer

trace-cmd reset
sleep 0.5
echo "clear the trace buffers"

echo 0 > /sys/kernel/debug/tracing/tracing_on
sleep 0.5
echo "tracing_off"

echo 0 > /sys/kernel/debug/tracing/events/enable
sleep 0.5
echo "events disabled"

echo nop > /sys/kernel/debug/tracing/current_tracer
sleep 0.5
echo "nop tracer enabled"

echo $BUFFER_SIZE > /sys/kernel/debug/tracing/buffer_size_kb
sleep 0.5
echo "Size of ftrace buffer = "$BUFFER_SIZE

# echo 1 > /sys/kernel/debug/tracing/events/sched/sched_wakeup/enable
echo 1 > /sys/kernel/debug/tracing/events/sched/sched_switch/enable
# echo 1 > /sys/kernel/debug/tracing/events/sched/sched_pi_setprio/enable
sleep 0.5
echo "sched events enabled"

echo 1 > /sys/kernel/debug/tracing/tracing_on
echo "tracing on"
