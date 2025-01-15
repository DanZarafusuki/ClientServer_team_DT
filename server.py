import socket
import threading
import struct
import time
import sys
import signal

import colorama
from colorama import Fore, Style

MAGIC_COOKIE = 0xabcddcba
OFFER_MESSAGE_TYPE = 0x2
REQUEST_MESSAGE_TYPE = 0x3
PAYLOAD_MESSAGE_TYPE = 0x4

UDP_PORT = 13117
TCP_PORT = 20000
BUFFER_SIZE = 1024
BROADCAST_INTERVAL = 1

# An event we can use to signal threads to stop
stop_event = threading.Event()


def get_active_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
        return ip_address
    except Exception as e:
        print(f"{Fore.RED}Error retrieving active IP: {e}{Style.RESET_ALL}")
        return "127.0.0.1"


def send_offers():
    """
    Continuously sends UDP broadcast offers to potential clients
    until we are told to stop.
    """
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    message = struct.pack('!IBHH', MAGIC_COOKIE, OFFER_MESSAGE_TYPE, UDP_PORT, TCP_PORT)

    try:
        while not stop_event.is_set():
            udp_socket.sendto(message, ('<broadcast>', UDP_PORT))
            time.sleep(BROADCAST_INTERVAL)
    except OSError:
        # Likely socket closed during shutdown; ignore
        pass
    except Exception as e:
        print(f"{Fore.RED}[Offer Thread] Error sending offer: {e}{Style.RESET_ALL}")
    finally:
        udp_socket.close()


def handle_tcp_client(conn, addr):
    """
    Handle a single TCP connection in a separate thread.
    """
    try:
        data = conn.recv(BUFFER_SIZE).decode().strip()
        file_size = int(data)
        print(f"{Fore.YELLOW}TCP request from {addr}, requesting {file_size} bytes...{Style.RESET_ALL}\n", end='')

        chunk_size = 4096
        bytes_sent = 0

        while bytes_sent < file_size:
            remaining = file_size - bytes_sent
            to_send = min(chunk_size, remaining)
            conn.sendall(b'0' * to_send)
            bytes_sent += to_send

        print(f"{Fore.GREEN}TCP transfer to {addr} complete.{Style.RESET_ALL}\n", end='')

    except Exception as e:
        print(f"{Fore.RED}Error in TCP client {addr}: {e}{Style.RESET_ALL}")
    finally:
        conn.close()


def handle_udp_request(data, client_addr, udp_socket):
    """
    Handle a single UDP request in a separate thread.
    """
    try:
        if len(data) < 13:
            return
        magic_cookie, message_type, file_size = struct.unpack('!IBQ', data[:13])
        if magic_cookie != MAGIC_COOKIE or message_type != REQUEST_MESSAGE_TYPE:
            return

        total_segments = file_size // BUFFER_SIZE
        if file_size % BUFFER_SIZE != 0:
            total_segments += 1

        for segment_index in range(total_segments):
            payload_header = struct.pack('!IBQQ', MAGIC_COOKIE, PAYLOAD_MESSAGE_TYPE, total_segments, segment_index)
            payload = payload_header + b'X' * (BUFFER_SIZE - len(payload_header))
            udp_socket.sendto(payload, client_addr)

    except Exception as e:
        print(f"{Fore.RED}Error handling UDP request: {e}{Style.RESET_ALL}")


def accept_tcp_connections(tcp_socket):
    """
    Runs in its own thread and continuously accepts new TCP connections.
    Spawns a new thread for each client.
    """
    while not stop_event.is_set():
        try:
            conn, addr = tcp_socket.accept()
        except OSError:
            # Socket likely closed, exit thread quietly
            break
        except Exception as e:
            print(f"{Fore.RED}Error accepting TCP connection: {e}{Style.RESET_ALL}")
            continue

        print(f"{Fore.CYAN}New TCP connection from {addr}.{Style.RESET_ALL}\n", end='')
        threading.Thread(
            target=handle_tcp_client,
            args=(conn, addr),
            daemon=True
        ).start()


def udp_requests_handler(udp_socket):
    """
    Runs in its own thread and continuously receives UDP data.
    Spawns a new thread for each UDP request.
    """
    while not stop_event.is_set():
        try:
            data, client_addr = udp_socket.recvfrom(BUFFER_SIZE)
        except OSError:
            # Socket likely closed, exit thread quietly
            break
        except Exception as e:
            print(f"{Fore.RED}Error receiving UDP data: {e}{Style.RESET_ALL}")
            continue

        threading.Thread(
            target=handle_udp_request,
            args=(data, client_addr, udp_socket),
            daemon=True
        ).start()


def shutdown(tcp_socket, udp_socket):
    """
    Called during shutdown to close sockets and set the stop_event.
    """
    # Tell threads to exit their loops
    stop_event.set()

    # Closing sockets will make accept() and recvfrom() throw OSError
    try:
        tcp_socket.close()
    except:
        pass
    try:
        udp_socket.close()
    except:
        pass


def start_server():
    colorama.init(autoreset=True)

    ip_address = get_active_ip()
    print(f"{Fore.GREEN}Server started, IP address: {ip_address}{Style.RESET_ALL}")

    # 1) Thread to broadcast UDP offers
    offers_thread = threading.Thread(target=send_offers, daemon=True)
    offers_thread.start()

    # 2) TCP server setup
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp_socket.bind(('', TCP_PORT))
    tcp_socket.listen(50)

    # 3) UDP server setup
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_socket.bind(('', UDP_PORT))

    print(f"{Fore.BLUE}Listening on TCP:{TCP_PORT} and UDP:{UDP_PORT}.{Style.RESET_ALL}")

    # Start the TCP acceptor thread
    tcp_acceptor_thread = threading.Thread(
        target=accept_tcp_connections,
        args=(tcp_socket,),
        daemon=True
    )
    tcp_acceptor_thread.start()

    # Start the UDP requests handler thread
    udp_handler_thread = threading.Thread(
        target=udp_requests_handler,
        args=(udp_socket,),
        daemon=True
    )
    udp_handler_thread.start()

    # Graceful shutdown handler
    def handle_ctrl_c(signum, frame):
        print(f"\n{Fore.RED}CTRL+C detected. Shutting down gracefully...{Style.RESET_ALL}")
        shutdown(tcp_socket, udp_socket)
        # Wait a moment to let threads exit cleanly (optional)
        time.sleep(0.5)
        sys.exit(0)

    # Register the signal handler for Ctrl+C
    signal.signal(signal.SIGINT, handle_ctrl_c)

    try:
        while True:
            # Main thread can just sleep until interrupted
            time.sleep(1)
    except KeyboardInterrupt:
        # Fallback if signal doesn’t work on some OS/Python combos
        print(f"\n{Fore.RED}KeyboardInterrupt detected. Shutting down gracefully...{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Unexpected error in server: {e}{Style.RESET_ALL}")
    finally:
        shutdown(tcp_socket, udp_socket)
        sys.exit(0)


if __name__ == "__main__":
    start_server()
