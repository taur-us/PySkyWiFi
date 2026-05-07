import time
from abc import ABC, abstractmethod


class Transport(ABC):

    @abstractmethod
    def send(self, inp: str):
        pass

    @abstractmethod
    def recv(self) -> str:
        pass

    @abstractmethod
    def segment_data_size(self) -> int:
        pass

    @abstractmethod
    def sleep_for(self) -> float:
        pass

    def connect_send(self):
        pass

    def connect_recv(self):
        self.send("READY")

    def is_ready(self) -> bool:
        return self.recv() == "READY"

    def close(self):
        self.send("END")


class Protocol:

    def __init__(self, send_pipe, rcv_pipe):
        self.send_pipe = send_pipe
        self.rcv_pipe = rcv_pipe

    def connect(self):
        self.send_pipe.connect_send()
        self.rcv_pipe.connect_recv()

    def close(self):
        self.rcv_pipe.close()

    def send(self, inp: str):
        # Wait until the receiver is ready
        while True:
            if self.send_pipe.is_ready():
                break
            time.sleep(self.send_pipe.sleep_for())

        # Send entire message in one write, wait for ACK
        self.send_pipe.send(inp)
        while True:
            raw = self.rcv_pipe.recv()
            if raw == "ACK":
                break
            time.sleep(self.rcv_pipe.sleep_for())

        self.send_pipe.send("END")

    def recv(self) -> str:
        while True:
            raw = self.rcv_pipe.recv()
            if raw and raw not in ("READY", "END", "ACK", ""):
                self.send_pipe.send("ACK")
                return raw
            if raw == "END":
                return ""
            time.sleep(self.rcv_pipe.sleep_for())

    def recv_and_sleep(self) -> str:
        return self.recv()
