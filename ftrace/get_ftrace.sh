#!/bin/bash

echo 0 > /sys/kernel/debug/tracing/tracing_on
echo "ftrace off"

sleep 3
cp /sys/kernel/debug/tracing/trace .
mv trace $HOME/git/instance_contention_research/log/ftrace_log.txt
