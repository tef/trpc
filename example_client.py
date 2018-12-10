import trpc
import sys

example = trpc.open(sys.argv[1])

print(example.Example.hello())
