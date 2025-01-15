# client.py
"""
Client Program

The client listens for broadcast offers from the server on a specified UDP port.
Once the file size and number of connections (TCP and UDP) are set, the client reuses them for subsequent transfers.
"""

import socket
import threading
import struct
import time
import sys

# For colored output
import colorama
from colorama import Fore, Style

# consts
MAGIC_COOKIE = 0xabcddcba  # Unique identifier for the magic cookie
OFFER_MESSAGE_TYPE = 0x2  # Indicates a broadcast message offering service
REQUEST_MESSAGE_TYPE = 0x3  # Indicates a client request for file transfer
UDP_PORT = 13117  # Default UDP port for broadcasting and receiving
BUFFER_SIZE = 1024  # Size of the buffer for data transfer

BROADCAST_INTERVAL = 1  # Interval (seconds) for sending UDP broadcast

# Global settings
file_size = None
tcp_connections = None
udp_connections = None


def prompt_settings():
    """Prompts the user for file size and number of connections if not set."""
    global file_size, tcp_connections, udp_connections

    if file_size is None:
        file_size = int(input(f"{Fore.YELLOW}Enter file size (in bytes): {Style.RESET_ALL}"))
    if tcp_connections is None:
        tcp_connections = int(input(f"{Fore.YELLOW}Enter number of TCP connections: {Style.RESET_ALL}"))
    if udp_connections is None:
        udp_connections = int(input(f"{Fore.YELLOW}Enter number of UDP connections: {Style.RESET_ALL}"))


def start_client():
    """
    Starts the client:
      1. Creates and binds a UDP socket to listen for server offers on UDP_PORT.
      2. When an offer is received, starts data transfers using the predefined settings.
      3. Awaits new server offers after transfers complete.
    """
    # Initialize colorama for colored console output
    colorama.init(autoreset=True)

    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_socket.bind(('', UDP_PORT))

    print(f"{Fore.GREEN}Client started, listening for offer requests...{Style.RESET_ALL}")

    try:
        while True:
            data, server_address = udp_socket.recvfrom(BUFFER_SIZE)

            # Validate length of data
            if len(data) < 9:
                continue

            # Unpack the server’s broadcast data
            magic_cookie, message_type, udp_port, tcp_port = struct.unpack('!IBHH', data[:9])

            # Validate the magic cookie and message type
            if magic_cookie != MAGIC_COOKIE or message_type != OFFER_MESSAGE_TYPE:
                continue

            print(
                f"{Fore.CYAN}Received offer from {server_address[0]}, "
                f"attempting to connect...{Style.RESET_ALL}"
            )

            # Ensure settings are configured
            prompt_settings()

            # Create threads for each TCP connection
            threads = []
            for i in range(tcp_connections):
                t = threading.Thread(
                    target=perform_tcp_transfer,
                    args=(server_address[0], tcp_port, file_size, i + 1),
                    daemon=True
                )
                threads.append(t)

            # Create threads for each UDP connection
            for i in range(udp_connections):
                t = threading.Thread(
                    target=perform_udp_transfer,
                    args=(server_address[0], udp_port, file_size, i + 1),
                    daemon=True
                )
                threads.append(t)

            # Start and join all threads
            for thread in threads:
                thread.start()

            for thread in threads:
                thread.join()

            print(f"{Fore.GREEN}All transfers complete, listening for new offer requests...{Style.RESET_ALL}")
    except KeyboardInterrupt:
        print(f"\n{Fore.RED}Client shutting down...{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Unexpected error in client: {e}{Style.RESET_ALL}")
    finally:
        udp_socket.close()
        sys.exit(0)


def perform_tcp_transfer(server_ip, server_port, file_size, connection_id):
    """
    Performs a TCP transfer:
      1. Connects to server on TCP port.
      2. Sends file size request.
      3. Receives dummy data until the end.
      4. Calculates total time taken and transfer speed in bits/second.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_socket:
            tcp_socket.connect((server_ip, server_port))
            tcp_socket.sendall(f"{file_size}\n".encode())

            start_time = time.time()

            # Receive data until there's no more
            while True:
                received_data = tcp_socket.recv(BUFFER_SIZE)
                if not received_data:
                    break

            end_time = time.time()

            total_time = end_time - start_time
            # Transfer speed in bits per second
            transfer_speed = (file_size * 8) / total_time if total_time > 0 else 0

            print(
                f"{Fore.MAGENTA}TCP transfer #{connection_id} finished. "
                f"Time: {total_time:.2f}s, Speed: {transfer_speed:.2f} bits/s{Style.RESET_ALL}\n", end=''
            )
    except Exception as e:
        print(f"{Fore.RED}Error during TCP transfer #{connection_id}: {e}{Style.RESET_ALL}")


def perform_udp_transfer(server_ip, server_port, file_size, connection_id):
    """
    Performs a UDP transfer:
      1. Sends a request packet with file size to server.
      2. Receives data until a socket timeout occurs.
      3. Calculates total time, transfer speed, and success rate.
    """
    try:
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Request packet format: [MAGIC_COOKIE][REQUEST_MESSAGE_TYPE][file_size]
        request_packet = struct.pack('!IBQ', MAGIC_COOKIE, REQUEST_MESSAGE_TYPE, file_size)
        udp_socket.sendto(request_packet, (server_ip, server_port))

        start_time = time.time()
        total_bytes_received = 0

        # Continuously attempt to receive data until a timeout
        while True:
            try:
                udp_socket.settimeout(1)
                data, _ = udp_socket.recvfrom(BUFFER_SIZE)
                total_bytes_received += len(data)
            except socket.timeout:
                # No more data coming
                break

        end_time = time.time()
        total_time = end_time - start_time

        # Transfer speed in bits per second
        transfer_speed = (total_bytes_received * 8) / total_time if total_time > 0 else 0
        success_rate = min(100, (total_bytes_received / file_size) * 100) if file_size else 0

        print(
            f"{Fore.MAGENTA}UDP transfer #{connection_id} finished. "
            f"Time: {total_time:.2f}s, Speed: {transfer_speed:.2f} bits/s, "
            f"Success Rate: {success_rate:.2f}%{Style.RESET_ALL}\n", end=''
        )
    except Exception as e:
        print(f"{Fore.RED}Error during UDP transfer #{connection_id}: {e}{Style.RESET_ALL}")


if __name__ == "__main__":
    start_client()
