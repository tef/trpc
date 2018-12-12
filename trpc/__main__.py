import sys
import os

from . import client, cli

if __name__ == '__main__':
    session = client.Session()
    cli = cli.CLI(session)
    cli.main(sys.argv[1:], os.environ)
