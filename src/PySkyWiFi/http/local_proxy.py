import socket
import base64

from PySkyWiFi import Protocol


def receive_http_request(recv):
    request_data = ""
    while True:
        chunk = recv()
        if not chunk:
            break
        request_data += chunk
        if "\r\n\r\n" in request_data:
            headers, rest = request_data.split('\r\n\r\n', 1)
            if 'Content-Length: ' in headers:
                content_length = int(headers.split('Content-Length: ')[1].split('\r\n')[0])
                while len(rest) < content_length:
                    rest += recv()
            request_data = headers + '\r\n\r\n' + rest
            break
    return request_data


def receive_http_response(recv):
    response_data = ""
    while True:
        chunk = recv()
        if not chunk:
            break
        response_data += chunk
        if "\r\n\r\n" in response_data:
            headers, rest = response_data.split('\r\n\r\n', 1)
            if 'Content-Length: ' in headers:
                content_length = int(headers.split('Content-Length: ')[1].split('\r\n')[0])
                while len(rest) < content_length:
                    rest += recv()
                response_data = headers + '\r\n\r\n' + rest
                break
            elif 'Transfer-Encoding: chunked' in headers:
                while True:
                    if '\r\n' in rest:
                        size_hex, rest = rest.split('\r\n', 1)
                        size = int(size_hex, 16)
                        if size == 0:
                            break
                        while len(rest) < size:
                            rest += recv()
                        rest = rest[size:]
                        if '\r\n' in rest:
                            rest = rest.split('\r\n', 1)[1]
                response_data = headers + '\r\n\r\n' + rest
                break
    return response_data


def handle_connect(client_connection, host, port, protocol):
    """Handle HTTP CONNECT tunnel request for HTTPS."""
    # Tell browser the tunnel is established
    client_connection.send(b"HTTP/1.1 200 Connection established\r\n\r\n")

    # Now relay raw bytes between browser and remote via PySkyWiFi
    # Collect all data from browser until it pauses, then tunnel it
    client_connection.settimeout(0.5)
    raw = b""
    while True:
        try:
            chunk = client_connection.recv(4096)
            if not chunk:
                break
            raw += chunk
        except socket.timeout:
            break

    if not raw:
        return

    # Send as base64 over PySkyWiFi with CONNECT metadata prefix
    payload = f"CONNECT {host}:{port}\r\n\r\n" + base64.b64encode(raw).decode()

    try:
        protocol.connect()
        protocol.send(payload)
        response_b64 = protocol.recv_and_sleep()
        if response_b64:
            response = base64.b64decode(response_b64.encode())
            client_connection.send(response)
        client_connection.close()
    finally:
        protocol.close()


def run(protocol: Protocol, port: int=9090):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('localhost', port))
    server_socket.listen(5)
    print(f"Server is listening on port {port}...")

    try:
        while True:
            client_connection, _ = server_socket.accept()
            try:
                # Peek at the first line to detect CONNECT
                first_data = client_connection.recv(4096, socket.MSG_PEEK).decode('utf-8', errors='replace')
                first_line = first_data.split('\r\n')[0]

                if first_line.startswith('CONNECT '):
                    # Consume the full headers
                    buf = b""
                    while b"\r\n\r\n" not in buf:
                        buf += client_connection.recv(1)
                    parts = first_line.split(' ')
                    host_port = parts[1]
                    host, port_str = host_port.rsplit(':', 1)
                    handle_connect(client_connection, host, int(port_str), protocol)
                else:
                    request_data = receive_http_request(lambda: client_connection.recv(1024).decode('utf-8'))
                    try:
                        protocol.connect()
                        protocol.send(request_data)
                        res = receive_http_response(protocol.recv_and_sleep)
                        client_connection.send(res.encode('utf-8'))
                        client_connection.close()
                    finally:
                        protocol.close()
            except Exception as e:
                print(f"[!] Error handling request: {e}")
                try:
                    client_connection.close()
                except Exception:
                    pass
    finally:
        server_socket.close()
