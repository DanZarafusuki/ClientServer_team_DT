import socket
import struct
import select
MAGIC_COOKIE = 0xabcddcba
MESSAGE_TYPE_OFFER = 0x2
PACKET_SIZE = 1024


def listen_for_offers(udp_socket):
    while True:
        ready_sockets, _, _ = select.select([udp_socket], [], [], None)
        for sock in ready_sockets:
            data, addr = sock.recvfrom(1024)
            magic_cookie, msg_type, udp_port, tcp_port = struct.unpack('!IBHH', data)
            if magic_cookie == MAGIC_COOKIE and msg_type == MESSAGE_TYPE_OFFER:
                print(f"Valid offer from {addr[0]}")
                return addr[0], tcp_port, udp_port


def handle_tcp_connection(server_ip, tcp_port):
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.connect((server_ip, tcp_port))
    tcp_socket.sendall(b"Hello Server")  # Placeholder for file size
    tcp_socket.close()
