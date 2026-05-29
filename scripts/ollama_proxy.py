#!/usr/bin/env python3
"""A simple, zero-dependency Python TCP port-forwarding proxy.

Used to bridge connections from inside Docker containers (connecting to the host gateway IP)
to host services bound exclusively to 127.0.0.1 (such as a local Ollama instance).
"""

import socket
import sys
import threading

def handle_client(client_socket, remote_host, remote_port):
    remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        remote_socket.connect((remote_host, remote_port))
    except Exception as e:
        print(f"Failed to connect to remote service at {remote_host}:{remote_port}: {e}", flush=True)
        client_socket.close()
        return

    def forward(source, destination):
        try:
            while True:
                data = source.recv(4096)
                if not data:
                    break
                destination.sendall(data)
        except Exception:
            pass
        finally:
            source.close()
            destination.close()

    t1 = threading.Thread(target=forward, args=(client_socket, remote_socket), daemon=True)
    t2 = threading.Thread(target=forward, args=(remote_socket, client_socket), daemon=True)
    t1.start()
    t2.start()

def main():
    if len(sys.argv) < 5:
        print("Usage: ollama_proxy.py <local_host> <local_port> <remote_host> <remote_port>", flush=True)
        sys.exit(1)

    local_host = sys.argv[1]
    local_port = int(sys.argv[2])
    remote_host = sys.argv[3]
    remote_port = int(sys.argv[4])

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((local_host, local_port))
    except Exception as e:
        print(f"Failed to bind proxy to {local_host}:{local_port}: {e}", flush=True)
        sys.exit(1)

    server.listen(100)
    print(f"Proxy listening on {local_host}:{local_port} -> {remote_host}:{remote_port}", flush=True)

    try:
        while True:
            client_socket, addr = server.accept()
            handle_client(client_socket, remote_host, remote_port)
    except KeyboardInterrupt:
        pass
    finally:
        server.close()

if __name__ == '__main__':
    main()
