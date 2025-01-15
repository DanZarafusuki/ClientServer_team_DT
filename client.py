# client.py
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
BUFFER_SIZE = 1024


def start_client():
    """Starts the client and listens for server offers."""
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_socket.bind(('', UDP_PORT))

    print("Client started, listening for offer requests...")

    while True:
        data, server_address = udp_socket.recvfrom(BUFFER_SIZE)
        if len(data) < 9:
            continue

        magic_cookie, message_type, udp_port, tcp_port = struct.unpack('!IBHH', data[:9])
        if magic_cookie != MAGIC_COOKIE or message_type != OFFER_MESSAGE_TYPE:
            continue

        print(f"Received offer from {server_address[0]}, attempting to connect...")

        # Prompt user for parameters
        file_size = int(input("Enter file size (in bytes): "))
        tcp_connections = int(input("Enter number of TCP connections: "))
        udp_connections = int(input("Enter number of UDP connections: "))

        # Start transfers
        threads = []
        for i in range(tcp_connections):
            threads.append(
                threading.Thread(target=perform_tcp_transfer, args=(server_address[0], tcp_port, file_size, i + 1)))
        for i in range(udp_connections):
            threads.append(
                threading.Thread(target=perform_udp_transfer, args=(server_address[0], udp_port, file_size, i + 1)))

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        print("All transfers complete, listening to offer requests...")


def perform_tcp_transfer(server_ip, server_port, file_size, connection_id):
    """Performs a TCP transfer with the server."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_socket:
            tcp_socket.connect((server_ip, server_port))
            tcp_socket.sendall(f"{file_size}\n".encode())

            start_time = time.time()
            received_data = tcp_socket.recv(BUFFER_SIZE)
            while received_data:
                received_data = tcp_socket.recv(BUFFER_SIZE)
            end_time = time.time()

            total_time = end_time - start_time
            transfer_speed = file_size * 8 / total_time  # in bits/second
            print(
                f"TCP transfer #{connection_id} finished, total time: {total_time:.2f} seconds, total speed: {transfer_speed:.2f} bits/second")
    except Exception as e:
        print(f"Error during TCP transfer #{connection_id}: {e}")


def perform_udp_transfer(server_ip, server_port, file_size, connection_id):
    """Performs a UDP transfer with the server."""
    try:
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        request_packet = struct.pack('!IBQ', MAGIC_COOKIE, REQUEST_MESSAGE_TYPE, file_size)
        udp_socket.sendto(request_packet, (server_ip, server_port))

        start_time = time.time()
        total_bytes_received = 0
        while True:
            try:
                udp_socket.settimeout(1)
                data, _ = udp_socket.recvfrom(BUFFER_SIZE)
                total_bytes_received += len(data)
            except socket.timeout:
                break
        end_time = time.time()

        total_time = end_time - start_time
        transfer_speed = (total_bytes_received * 8) / total_time  # in bits/second
        success_rate = min(100, (total_bytes_received / file_size) * 100)
        print(
            f"UDP transfer #{connection_id} finished, total time: {total_time:.2f} seconds, total speed: {transfer_speed:.2f} bits/second, percentage of packets received successfully: {success_rate:.2f}%")
    except Exception as e:
        print(f"Error during UDP transfer #{connection_id}: {e}")


if __name__ == "__main__":
    start_client()
