#!/usr/bin/env python3

import trpc
import sys

example = trpc.open(sys.argv[1])

print(example.Example.hello())
