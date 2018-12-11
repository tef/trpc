#!/bin/bash
export TRPC_URL="$1"
export PYTHONPATH=`dirname "$0"`
python3 -m trpc Example:hello
