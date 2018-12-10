import sys
import os

from . import client, cli

if __name__ == '__main__':
    client = client.Client()
    cli = cli.CLI(client)
    cli.main(sys.argv[1:], os.environ)
