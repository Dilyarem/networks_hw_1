import socket

class UDPBasedProtocol:
    def __init__(self, *, local_addr, remote_addr):
        self.udp_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self.remote_addr = remote_addr
        self.udp_socket.bind(local_addr)

    def sendto(self, data):
        return self.udp_socket.sendto(data, self.remote_addr)

    def recvfrom(self, n):
        msg, addr = self.udp_socket.recvfrom(n)
        return msg


class Segment:
    def __init__(self, seq_num: int, ack_num: int, data: bytes = b""):
        self.seq_num = seq_num
        self.ack_num = ack_num
        self.data = data

    def dumps(self) -> bytes:
        seq = self.seq_num.to_bytes(4, "big")
        ack = self.ack_num.to_bytes(4, "big")
        return seq + ack + self.data

    @staticmethod
    def loads(data: bytes):
        seq = int.from_bytes(data[:4], "big")
        ack = int.from_bytes(data[4:8], "big")
        return Segment(seq, ack, data[8:])


HEADER_SIZE = 8
MAX_DATA_SIZE = 2**15 - 8

class MyTCPProtocol(UDPBasedProtocol):
    def __init__(self, *args, **kwargs):
        self.seq_num = 0
        self.ack_num = 0
        self._received = []
        super().__init__(*args, **kwargs)
        self.udp_socket.settimeout(0.01)

    def send(self, data: bytes):
        bytes_sent = 0
        while bytes_sent < len(data):
            max_size = min(len(data), MAX_DATA_SIZE - 8 + bytes_sent)
            segment = Segment(self.seq_num, self.ack_num, data[bytes_sent: max_size])
            self.seq_num += len(segment.data)
            self.sendto(segment.dumps())
            bytes_sent = max_size
            while True:
                try:
                    answer = Segment.loads(self.recvfrom(8))
                    if answer.ack_num >= self.seq_num:
                        break
                except socket.error:
                    self.sendto(segment.dumps())

        return len(data)

    def recv(self, n: int):
        data = b""
        while len(data) < n:
            try:
                segment = Segment.loads(self.recvfrom(n + 8))
                self._received.append(segment)
            except socket.error:
                self._ack()

            self._received.sort(key=lambda seg: seg.seq_num)
            while len(self._received) != 0:
                if self.ack_num >= self._received[0].seq_num:
                    if self.ack_num == self._received[0].seq_num:
                        self.ack_num = self._received[0].seq_num + len(self._received[0].data)
                        data += self._received[0].data
                        self._ack()
                    self._received.pop(0)
                else:
                    break

        return data

    def _ack(self):
        segment = Segment(self.seq_num, self.ack_num)
        self.sendto(segment.dumps())
