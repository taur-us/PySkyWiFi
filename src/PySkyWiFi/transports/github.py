import base64
import github
from PySkyWiFi import Transport
from PySkyWiFi.transports import load_config


class GithubTransport(Transport):

    def __init__(self, gist_id: str, token: str, fernet=None, sleep_for: float=0.5):
        self.gist_id = gist_id
        self._sleep_for = sleep_for
        self._fernet = fernet
        self._client = github.Github(auth=github.Auth.Token(token))
        self._gist = self._client.get_gist(gist_id)
        self._filename = list(self._gist.files)[0]

    @staticmethod
    def from_conf(block_id: int, sleep_for: float=0.5) -> "GithubTransport":
        conf = load_config()
        block = conf["github"][block_id]
        fernet = None
        if "key" in conf:
            from cryptography.fernet import Fernet
            fernet = Fernet(conf["key"].encode())
        return GithubTransport(block["gist_id"], block["token"], fernet, sleep_for)

    def send(self, inp: str):
        data = inp.encode()
        if self._fernet:
            data = self._fernet.encrypt(data)
            content = base64.b64encode(data).decode()
        else:
            content = base64.b64encode(data).decode()
        self._gist.edit(files={self._filename: github.InputFileContent(content=content)})

    def recv(self) -> str:
        self._gist = self._client.get_gist(self.gist_id)
        content = self._gist.files[self._filename].content
        if not content:
            return ""
        data = base64.b64decode(content.encode())
        if self._fernet:
            data = self._fernet.decrypt(data)
        return data.decode()

    def sleep_for(self) -> float:
        return self._sleep_for

    def segment_data_size(self) -> int:
        return 65536
