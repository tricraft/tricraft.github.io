#!/usr/bin/env python3

import http.client
import json
import logging
import os
from pathlib import Path
import socket
import threading
import time
import traceback
import urllib.parse

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s: %(message)s")


def transfer(src, dst, direction):
    src_address, src_port = src.getsockname()
    dst_address, dst_port = dst.getsockname()
    while True:
        try:
            buffer = src.recv(4096)
            if not buffer:
                break
            dst.sendall(buffer)
        except Exception as e:
            break
    dst.close()

def connect(remote_host, remote_port, src_socket, src_address):
    try:
        dst_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        dst_socket.settimeout(30)
        dst_socket.connect((remote_host, remote_port))
        s = threading.Thread(target=transfer, args=(dst_socket, src_socket, False))
        r = threading.Thread(target=transfer, args=(src_socket, dst_socket, True))
        s.start()
        r.start()
    except Exception as e:
        try:
            dst_socket.close()
        except KeyboardInterrupt:
            raise
        except:
            pass
        try:
            src_socket.close()
        except KeyboardInterrupt:
            raise
        except:
            pass

def server(local_host, local_port, remote_host, remote_port):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((local_host, local_port))
    server_socket.listen(64)
    logging.info(f"Forwarding: {local_host, local_port} -> {remote_host, remote_port}")
    while True:
        src_socket, src_address = server_socket.accept()
        src_socket.settimeout(30)
        conn = threading.Thread(target=connect, args=(remote_host, remote_port, src_socket, src_address))
        conn.start()

def request(hostname, key):
    conn = http.client.HTTPSConnection(hostname)
    conn.request("POST", "/start", body="password=" + urllib.parse.quote(key))
    r = conn.getresponse()
    conn.close()
    if r.status != 200:
        raise RuntimeError("HTTP status " + str(r.status) + ". Try again later.")
    print("Start requested. It may take several minutes (vanilla: <1 minute; modded: <8 minutes) for the server to start.")

    print("Getting server IP.")
    for _ in range(11):
        conn = http.client.HTTPSConnection(hostname)
        conn.request("POST", "/query_ip", body="password=" + urllib.parse.quote(key))
        r = conn.getresponse()
        if r.status != 200:
            conn.close()
            raise RuntimeError("HTTP status " + str(r.status) + ". Try again later.")
        data = r.read()
        conn.close()
        if data != b"null":
            data = data.decode("utf-8")
            print("Server IP: " + data)
            return data
        time.sleep(2)
    raise RuntimeError("Failed to get server IP. Try again later")

def run():
    home = Path.home()

    if os.path.exists("mc_server.json"):
        config = "mc_server.json"
    else:
        directory = os.path.join(home, ".mc_server")
        directory_exists = os.path.exists(directory)
        config = os.path.join(directory, "mc_server.json")
        config_exists = os.path.exists(config)
        if not directory_exists or not config_exists:
            print(f"Enter server URL. It will be saved at \"{config}\".")
            url = input()
            url = url.strip("\r\n")
            print(f"Enter server key. It will be saved at \"{config}\".")
            key = input()
            key = key.strip("\r\n")
            if not directory_exists:
                os.mkdir(directory)
            with open(config, "w") as f:
                f.write(json.dumps({"version": 1, "url": url, "key": key}) + "\n")

    with open(config, "r") as f:
        config = json.loads(f.read())

    url = config["url"]
    key = config["key"]

    hostname = urllib.parse.urlparse(url).netloc
    server_ip = request(hostname, key)

    threads = []
    for port in [1910, 1911, 1912]:
        t = threading.Thread(target=server, args=("127.0.0.1", port, server_ip, port))
        t.daemon = True
        t.start()
        threads.append(t)
    for t in threads:
        t.join()

try:
    run()
except KeyboardInterrupt:
    raise
except:
    print(traceback.format_exc())
input()
