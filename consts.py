# consts.py
"""
This module holds constants used by both client and server.
"""

MAGIC_COOKIE = 0xabcddcba  # Unique identifier for the magic cookie
OFFER_MESSAGE_TYPE = 0x2  # Indicates a broadcast message offering service
REQUEST_MESSAGE_TYPE = 0x3  # Indicates a client request for file transfer
PAYLOAD_MESSAGE_TYPE = 0x4  # Indicates payload data in UDP transfer

UDP_PORT = 13117    # Default UDP port for broadcasting and receiving
TCP_PORT = 20000    # Default TCP port for connections
BUFFER_SIZE = 1024  # Size of the buffer for data transfer

BROADCAST_INTERVAL = 1  # Interval (seconds) for sending UDP broadcast
