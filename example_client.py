#!/usr/bin/env python3
"""
run ./example_client.py http://localhost:1729/
"""

import trpc
import sys

example = trpc.open(sys.argv[1])

print(example.Example.hello(name="python"))
