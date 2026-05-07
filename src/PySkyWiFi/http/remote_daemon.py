import base64
import socket
from urllib.parse import urlparse

import httpx
from httpx import Request

from PySkyWiFi import Protocol
from PySkyWiFi.http.local_proxy import receive_http_request


def parse_request(request_data):
    headers = {}
    lines = request_data.split('\r\n')
    request_line = lines[0]
    method, full_path, _ = request_line.split()

    if '://' in full_path:
        scheme, rest = full_path.split('://', 1)
    else:
        scheme, rest = 'https', full_path
    url_parts = rest.split('/', 1)
    host = url_parts[0].split(':')[0]
    path = '/' + url_parts[1] if len(url_parts) > 1 else '/'

    i = 1
    while i < len(lines) and lines[i] and ':' in lines[i]:
        key, value = lines[i].split(':', 1)
        headers[key.strip()] = value.strip()
        i += 1
    body = '\r\n'.join(lines[i+1:])

    return method, scheme, host, path, headers, body


def send_http_request(request_data):
    method, _, _, _, headers, body = parse_request(request_data)
    url = headers["X-PySkyWiFi"]
    headers["Host"] = urlparse(url).hostname

    with httpx.Client() as client:
        request = Request(method, url, headers=headers, content=body.encode())
        response = client.send(request)
        resp_headers = "\r\n".join(
            f'{k}: {v}' for k, v in response.headers.items()
            if k.lower() != "transfer-encoding"
        )
        return f"HTTP/1.1 {response.status_code} {response.reason_phrase}\r\n" + resp_headers + "\r\n\r\n" + response.text + "\r\n\r\n"


def handle_connect(payload):
    """Handle a CONNECT tunnel: open real TCP connection, send raw bytes, return response."""
    header, b64_data = payload.split('\r\n\r\n', 1)
    host_port = header.replace('CONNECT ', '').strip()
    host, port_str = host_port.rsplit(':', 1)
    port = int(port_str)
    raw = base64.b64decode(b64_data.encode())

    try:
        with socket.create_connection((host, port), timeout=10) as s:
            s.sendall(raw)
            s.settimeout(2.0)
            response = b""
            while True:
                try:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    response += chunk
                except socket.timeout:
                    break
        return base64.b64encode(response).decode()
    except Exception as e:
        return base64.b64encode(f"Error: {e}".encode()).decode()


def run(protocol: Protocol):
    while True:
        try:
            protocol.connect()
            req = receive_http_request(protocol.recv_and_sleep)

            if req.startswith('CONNECT '):
                res = handle_connect(req)
            else:
                res = send_http_request(req)

            protocol.send(res)
        finally:
            protocol.close()
