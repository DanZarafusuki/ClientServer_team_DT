# server.py
"""
Server Program

The server broadcasts offers on a specified UDP port, waits for clients
to connect (both TCP and UDP), and sends requested dummy data back.
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
PAYLOAD_MESSAGE_TYPE = 0x4  # Indicates payload data in UDP transfer

UDP_PORT = 13117  # Default UDP port for broadcasting and receiving
TCP_PORT = 20000  # Default TCP port for connections
BUFFER_SIZE = 1024  # Size of the buffer for data transfer

BROADCAST_INTERVAL = 1  # Interval (seconds) for sending UDP broadcast


def get_active_ip():
    """
    Retrieve the active IP address of the machine for the desired network.
    This method attempts a UDP connection to a public IP (8.8.8.8) to fetch
    the local IP address that would be used on the internet.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  # Google's DNS
            ip_address = s.getsockname()[0]
        return ip_address
    except Exception as e:
        print(f"{Fore.RED}Error retrieving active IP: {e}{Style.RESET_ALL}")
        return "127.0.0.1"  # Default to localhost if an error occurs


def send_offers():
    """
    Continuously sends UDP broadcast offers to potential clients.
    Each offer includes:
      [MAGIC_COOKIE][OFFER_MESSAGE_TYPE][UDP_PORT][TCP_PORT]
    """
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Pack the message with magic cookie, message type, and ports
    message = struct.pack('!IBHH', MAGIC_COOKIE, OFFER_MESSAGE_TYPE, UDP_PORT, TCP_PORT)

    while True:
        try:
            # Broadcast to the entire subnet
            udp_socket.sendto(message, ('<broadcast>', UDP_PORT))
            time.sleep(BROADCAST_INTERVAL)
        except Exception as e:
            print(f"{Fore.RED}[Offer Thread] Error sending offer: {e}{Style.RESET_ALL}")


def handle_tcp_client(conn, addr):
    """
    Handles a single TCP client connection:
      1. Reads the file size from the client.
      2. Sends dummy data of that size back to the client in chunks.
    """
    try:
        # Receive the file size from the client
        data = conn.recv(BUFFER_SIZE).decode().strip()
        file_size = int(data)
        print(f"{Fore.YELLOW}TCP request received from {addr}, requesting {file_size} bytes...{Style.RESET_ALL}")

        # Send the requested data in chunks
        chunk_size = 4096  # Adjust chunk size if needed
        bytes_sent = 0

        while bytes_sent < file_size:
            # Calculate the size of the next chunk
            remaining = file_size - bytes_sent
            current_chunk_size = min(chunk_size, remaining)

            # Send the current chunk
            conn.sendall(b'0' * current_chunk_size)
            bytes_sent += current_chunk_size

        print(f"{Fore.GREEN}TCP transfer to {addr} complete.{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Error handling TCP client {addr}: {e}{Style.RESET_ALL}")
    finally:
        conn.close()



def handle_udp_request(data, client_addr, udp_socket):
    """
    Handles a single UDP request from a client:
      1. Unpacks request to validate magic cookie and message type.
      2. Calculates how many segments are needed for the requested file size.
      3. Sends segmented payload until file_size worth of data has been broadcast.
    """
    try:
        if len(data) < 13:
            return  # Invalid packet

        # Unpack the UDP request
        magic_cookie, message_type, file_size = struct.unpack('!IBQ', data[:13])
        if magic_cookie != MAGIC_COOKIE or message_type != REQUEST_MESSAGE_TYPE:
            return

        total_segments = file_size // BUFFER_SIZE + (1 if file_size % BUFFER_SIZE != 0 else 0)

        for segment in range(total_segments):
            # Prepare payload:
            #   [MAGIC_COOKIE][PAYLOAD_MESSAGE_TYPE][total_segments][segment_index] + padding
            payload_header = struct.pack('!IBQQ', MAGIC_COOKIE, PAYLOAD_MESSAGE_TYPE, total_segments, segment)
            # Fill the rest of the buffer with dummy data
            payload = payload_header + b'X' * (BUFFER_SIZE - len(payload_header))
            udp_socket.sendto(payload, client_addr)

    except Exception as e:
        print(f"{Fore.RED}Error handling UDP request: {e}{Style.RESET_ALL}")


def accept_tcp_connections(tcp_socket):
    """
    Continuously accepts new TCP client connections and spawns
    a thread to handle each connection.
    """
    while True:
        conn, addr = tcp_socket.accept()
        print(f"{Fore.CYAN}New TCP connection from {addr}.{Style.RESET_ALL}")
        threading.Thread(
            target=handle_tcp_client,
            args=(conn, addr),
            daemon=True
        ).start()


def start_server():
    """
    Starts the server:
      1. Determines the machine's active IP address.
      2. Spawns a thread to continuously broadcast UDP offers.
      3. Sets up a TCP socket to listen for client connections on TCP_PORT.
      4. Sets up a UDP socket to listen for client requests on UDP_PORT.
      5. Spawns threads to handle incoming connections and requests concurrently.
    """
    colorama.init(autoreset=True)

    ip_address = get_active_ip()
    print(f"{Fore.GREEN}Server started, listening on IP address {ip_address}{Style.RESET_ALL}")

    # Start UDP broadcast thread
    threading.Thread(target=send_offers, daemon=True).start()

    # Setup TCP server
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp_socket.bind(('', TCP_PORT))
    tcp_socket.listen(10)

    # Setup UDP server
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_socket.bind(('', UDP_PORT))

    print(f"{Fore.BLUE}Server is now listening for clients on TCP:{TCP_PORT} and UDP:{UDP_PORT}.{Style.RESET_ALL}")

    try:
        # Handle incoming connections/requests in an infinite loop
        while True:
            # Accept new TCP connections in a separate thread
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
                print(f"{Fore.RED}Error receiving UDP data: {e}{Style.RESET_ALL}")
    except KeyboardInterrupt:
        print(f"\n{Fore.RED}Server shutting down gracefully...{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Unexpected error in server: {e}{Style.RESET_ALL}")
    finally:
        tcp_socket.close()
        udp_socket.close()
        sys.exit(0)


if __name__ == "__main__":
    start_server()
