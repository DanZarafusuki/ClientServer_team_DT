# server.py
import socket
import threading
import struct
import time

from consts import (
    MAGIC_COOKIE,
    OFFER_MESSAGE_TYPE,
    REQUEST_MESSAGE_TYPE,
    PAYLOAD_MESSAGE_TYPE,
    UDP_PORT,
    TCP_PORT,
    BUFFER_SIZE,
    BROADCAST_INTERVAL,
)


def send_offers():
    """
    Sends UDP broadcast offers to potential clients.

    Continuously broadcasts an offer message containing the magic cookie,
    message type, and ports to inform clients about the server's availability.
    """
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    message = struct.pack('!IBHH', MAGIC_COOKIE, OFFER_MESSAGE_TYPE, UDP_PORT, TCP_PORT)

    while True:
        try:
            # Send broadcast to the entire subnet
            udp_socket.sendto(message, ('<broadcast>', UDP_PORT))
            time.sleep(BROADCAST_INTERVAL)
        except Exception as e:
            print(f"[Offer Thread] Error sending offer: {e}")


def handle_tcp_client(conn, addr):
    """
    Handles a single TCP client connection.

    Receives a file size request from the client, then sends dummy data
    of the requested size back to the client.
    """
    try:
        data = conn.recv(BUFFER_SIZE).decode().strip()
        file_size = int(data)
        print(f"TCP request received from {addr}, sending {file_size} bytes...")

        # Send the requested data
        conn.sendall(b'0' * file_size)
        print(f"TCP transfer to {addr} complete.")
    except Exception as e:
        print(f"Error handling TCP client {addr}: {e}")
    finally:
        conn.close()


def handle_udp_request(data, client_addr, udp_socket):
    """
    Handles a single UDP request from a client.

    Validates the client's request and sends payload data in segments
    based on the requested file size.
    """
    try:
        if len(data) < 13:
            return  # Invalid packet

        magic_cookie, message_type, file_size = struct.unpack('!IBQ', data[:13])
        if magic_cookie != MAGIC_COOKIE or message_type != REQUEST_MESSAGE_TYPE:
            return

        total_segments = file_size // BUFFER_SIZE + (
            1 if file_size % BUFFER_SIZE != 0 else 0
        )
        for segment in range(total_segments):
            # Prepare payload: [MAGIC_COOKIE][PAYLOAD_MESSAGE_TYPE][total_segments][segment_index] + padding
            payload_header = struct.pack(
                '!IBQQ', MAGIC_COOKIE, PAYLOAD_MESSAGE_TYPE, total_segments, segment
            )
            payload = payload_header + b'X' * (BUFFER_SIZE - len(payload_header))
            udp_socket.sendto(payload, client_addr)

    except Exception as e:
        print(f"Error handling UDP request: {e}")


def accept_tcp_connections(tcp_socket):
    """
    Accepts and handles incoming TCP client connections.

    Continuously accepts new client connections and spawns a thread
    to handle each client.
    """
    while True:
        conn, addr = tcp_socket.accept()
        threading.Thread(
            target=handle_tcp_client,
            args=(conn, addr),
            daemon=True
        ).start()


def start_server():
    """
    Starts the server for both TCP and UDP connections.

    Initializes a UDP socket for broadcasting and receiving requests, and
    a TCP socket for direct client communication. Spawns threads to
    handle concurrent client connections and requests.
    """
    ip_address = socket.gethostbyname(socket.gethostname())
    print(f"Server started, listening on IP address {ip_address}")

    # Start UDP broadcast thread
    threading.Thread(target=send_offers, daemon=True).start()

    # Setup TCP server
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp_socket.bind(('', TCP_PORT))
    tcp_socket.listen(5)

    # Setup UDP server
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_socket.bind(('', UDP_PORT))

    print("Server is listening for clients...")

    while True:
        # Accept new TCP connections
        threading.Thread(
            target=accept_tcp_connections,
            args=(tcp_socket,),
            daemon=True
        ).start()

        # Handle incoming UDP requests
        try:
            data, client_addr = udp_socket.recvfrom(BUFFER_SIZE)
            threading.Thread(
                target=handle_udp_request,
                args=(data, client_addr, udp_socket),
                daemon=True
            ).start()
        except Exception as e:
            print(f"Error receiving UDP data: {e}")


if __name__ == "__main__":
    start_server()
