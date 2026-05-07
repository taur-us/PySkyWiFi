import sys
import tempfile
import os

from PySkyWiFi import Protocol
from PySkyWiFi.transports.file import FileTransport
from PySkyWiFi.transports.github import GithubTransport
from PySkyWiFi.http.remote_daemon import run

TMPDIR = tempfile.gettempdir()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "github":
        print("Using GithubTransport...")
        p = Protocol(
            send_pipe=GithubTransport.from_conf(2),
            rcv_pipe=GithubTransport.from_conf(1),
        )
    else:
        print("Using FileTransport...")
        p = Protocol(
            send_pipe=FileTransport(fpath=os.path.join(TMPDIR, "pyskywifi_2")),
            rcv_pipe=FileTransport(fpath=os.path.join(TMPDIR, "pyskywifi_1")),
        )
    run(p)