import os.path
import socket
import struct
import json

import argparse

from server import walk_dir, send_chunk, recv_chunk


def recv_file(conn, file: str):
    data = conn.recv(4)
    size = struct.unpack('<i', data)[0]
    with open(file, "wb") as f:
        while size > 0:
            data = conn.recv(size)
            print("recv file {} / {}".format(size, len(data)))
            f.write(data)
            size = size - len(data)


parser = argparse.ArgumentParser(description='Tool for using common workspace')
parser.add_argument(
    'source_dir',
    type=str,
    default='.',
    help='name for source folder',
)

HOST = "127.0.0.1"
PORT = 38344

args = vars(parser.parse_args())
print("SYNC {}".format(args['source_dir']))
source = args['source_dir']

def cmd_init(client, source):
    print("exec init")
    filehash = walk_dir(source)
    content = json.dumps(filehash)
    send_chunk(client, content)

def cmd_update(client, source):
    print("exec update")
    filename = recv_chunk(client)
    recv_file(client, os.path.join(source, filename.decode("utf-8")))

table = {b"INIT": cmd_init,
         b"UPDATE": cmd_update}

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
    client.connect((HOST, PORT))
    while True:
        cmd = recv_chunk(client)
        print("receive {} command".format(cmd))
        if cmd in table.keys():
            table[cmd](client, source)