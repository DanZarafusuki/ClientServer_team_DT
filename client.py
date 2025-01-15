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
    print(f"Connecting to {server_ip}:{tcp_port}")
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.connect((server_ip, tcp_port))
    print("Sending test message")
    tcp_socket.sendall(b"Test Message")
    tcp_socket.close()
    print("Connection closed")


def handle_udp_connection(server_ip, udp_port):
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    request_message = struct.pack('!IBQ', MAGIC_COOKIE, MESSAGE_TYPE_OFFER, 1024)
    udp_socket.sendto(request_message, (server_ip, udp_port))

    received_data = 0
    try:
        while received_data < 1024:
            data, _ = udp_socket.recvfrom(2048)
            received_data += len(data)
            print(f"Received {len(data)} bytes")
    except socket.timeout:
        print("Timeout while receiving data")
    udp_socket.close()
