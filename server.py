import socket
import json
import hashlib
import struct
import argparse
import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import queue

def md5(file_path):
    hasher = hashlib.md5()
    with open(file_path, 'rb') as file:
        for chunk in iter(lambda: file.read(4096), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def send_chunk(conn, object):
    size = struct.pack("<i", len(object))
    conn.sendall(size)
    conn.sendall(object.encode('utf-8'))


def send_file(conn, folder: str, file: str):
    filepath = os.path.join(folder, file)
    print("send file size {}".format(os.path.getsize(filepath)))
    size = struct.pack("<i", os.path.getsize(filepath))
    conn.sendall(size)
    with open(filepath, "rb") as file:
        lines = file.readlines()
        for line in lines:
            print("s[{}]".format(line))
            conn.sendall(line)


def recv_chunk(conn):
    data = conn.recv(4)
    if len(data) == 0:
        print("close connection")
    size = struct.unpack('<i', data)[0]
    if size > 512:
        raise Exception
    data = conn.recv(size)
    return data

def walk_dir(folder: str):
    filehash = {}
    for address, dirs, files in os.walk(folder):
        print(": {}".format(files))
        for file in files:
            print("address {}".format(address))
            f = os.path.join(address, file)
            rel = os.path.relpath(f, folder)
            print("--- {}".format(rel))
            crc = md5(rel)
            filehash[rel] = crc
    return filehash


class MyHandler(FileSystemEventHandler):
    def __init__(self, source, queue):
        self.source = source
        self.queue = queue

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(".bin"):
            print(f"File {event.src_path} has been modified!")
            rel = os.path.relpath(event.src_path, self.source)
            print(f"File {rel} has been modified!")
            self.queue.put(rel)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Tool for using common workspace')
    parser.add_argument(
        'source_dir',
        type=str,
        default='.',
        help='name for source folder',
    )
    args = vars(parser.parse_args())

    queue = queue.Queue()
    source = args['source_dir']

    print("SYNC {}".format(source))
    HOST = "0.0.0.0"
    PORT = 38344

    # Create observer and event handler
    observer = Observer()
    event_handler = MyHandler(source, queue)

    # Set up observer to watch a specific directory
    observer.schedule(event_handler, source, recursive=True)

    # Start the observer
    observer.start()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as serv:
        serv.bind((HOST, PORT))
        serv.listen()
        conn, addr = serv.accept()
        with conn:
            print("connected by {}".format(addr))

            current = walk_dir(args['source_dir'])
            for i in current:
                print("file {} hash {}".format(i, current[i]))

            # INIT procedure
            send_chunk(conn, "INIT")
            data = recv_chunk(conn)
            filehash = json.loads(data)

            is_need_update = False
            for file in filehash:
                if file in current.keys():
                    print("file {} - {}".format(file, filehash[file]))
                    print("file {} - {}".format(file, current[file]))
                    is_need_update = filehash[file] == current[file]
                else:
                    is_need_update = True
                if is_need_update:
                    send_chunk(conn, "UPDATE")
                    send_chunk(conn, file)
                    send_file(conn, source, file)

            while True:
                time.sleep(1)
                if not queue.empty():
                    file = queue.get()
                    print("get file {}".format(file))
                    send_chunk(conn, "UPDATE")
                    send_chunk(conn, file)
                    send_file(conn, source, file)



