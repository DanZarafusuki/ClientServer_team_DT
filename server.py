# server.py
import socket
import threading
import struct
import time

# Constants
MAGIC_COOKIE = 0xabcddcba
OFFER_MESSAGE_TYPE = 0x2
REQUEST_MESSAGE_TYPE = 0x3
PAYLOAD_MESSAGE_TYPE = 0x4
UDP_PORT = 13117
TCP_PORT = 20000
BUFFER_SIZE = 1024


def send_offers():
    """Sends UDP broadcast offers to clients."""
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow port reuse

    message = struct.pack('!IBHH', MAGIC_COOKIE, OFFER_MESSAGE_TYPE, UDP_PORT, TCP_PORT)

    while True:
        udp_socket.sendto(message, ('<broadcast>', UDP_PORT))
        time.sleep(1)


def handle_tcp_client(conn, addr):
    """Handles a single TCP client connection."""
    try:
        data = conn.recv(BUFFER_SIZE).decode().strip()
        file_size = int(data)
        print(f"TCP request received from {addr}, sending {file_size} bytes.")

        # Send the requested data
        conn.sendall(b'0' * file_size)
        print(f"TCP transfer to {addr} complete.")
    except Exception as e:
        print(f"Error handling TCP client {addr}: {e}")
    finally:
        conn.close()


def handle_udp_request(data, client_addr, udp_socket):
    """Handles a single UDP request from a client."""
    try:
        if len(data) < 13:
            return  # Invalid packet

        magic_cookie, message_type, file_size = struct.unpack('!IBQ', data[:13])
        if magic_cookie != MAGIC_COOKIE or message_type != REQUEST_MESSAGE_TYPE:
            return

        total_segments = file_size // BUFFER_SIZE + (1 if file_size % BUFFER_SIZE != 0 else 0)
        for segment in range(total_segments):
            payload = struct.pack('!IBQQ', MAGIC_COOKIE, PAYLOAD_MESSAGE_TYPE, total_segments, segment)
            payload += b'X' * (BUFFER_SIZE - len(payload))
            udp_socket.sendto(payload, client_addr)
    except Exception as e:
        print(f"Error handling UDP request: {e}")


def start_server():
    """Starts the server for both TCP and UDP connections."""
    ip_address = socket.gethostbyname(socket.gethostname())
    print(f"Server started, listening on IP address {ip_address}")

    # Start UDP broadcast thread
    threading.Thread(target=send_offers, daemon=True).start()

    # Setup TCP server
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow port reuse for TCP
    tcp_socket.bind(('', TCP_PORT))
    tcp_socket.listen(5)

    # Setup UDP server
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow port reuse for UDP
    udp_socket.bind(('', UDP_PORT))

    print("Server is listening for clients...")

    while True:
        # Handle TCP connections
        threading.Thread(target=accept_tcp_connections, args=(tcp_socket,), daemon=True).start()

        # Handle UDP requests
        try:
            data, client_addr = udp_socket.recvfrom(BUFFER_SIZE)
            threading.Thread(target=handle_udp_request, args=(data, client_addr, udp_socket), daemon=True).start()
        except Exception as e:
            print(f"Error receiving UDP data: {e}")


def accept_tcp_connections(tcp_socket):
    """Accepts and handles TCP client connections."""
    while True:
        conn, addr = tcp_socket.accept()
        threading.Thread(target=handle_tcp_client, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    start_server()