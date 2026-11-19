"""Relay browser traffic through the server's authenticated HTTP proxy."""
import base64, select, socket, socketserver
from urllib.parse import urlsplit, unquote
from pathlib import Path
upstream = urlsplit(Path('/run/upstream').read_text().strip())
auth = base64.b64encode((unquote(upstream.username or '') + ':' + unquote(upstream.password or '')).encode()).decode()
class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(30)
        remote = None
        try:
            data = b''
            while b'\r\n\r\n' not in data:
                part = self.request.recv(8192)
                if not part: return
                data += part
                if len(data) > 65536: return
            head, body = data.split(b'\r\n\r\n', 1)
            lines = head.split(b'\r\n')
            lines = [line for line in lines if not line.lower().startswith(b'proxy-authorization:')]
            lines.append(('Proxy-Authorization: Basic ' + auth).encode())
            remote = socket.create_connection((upstream.hostname, upstream.port or 80), 20)
            remote.sendall(b'\r\n'.join(lines) + b'\r\n\r\n' + body)
            self.request.settimeout(None)
            remote.settimeout(None)
            while True:
                readable, _, _ = select.select([self.request, remote], [], [], 300)
                if not readable: return
                for source in readable:
                    part = source.recv(65536)
                    if not part: return
                    (remote if source is self.request else self.request).sendall(part)
        except (OSError, ValueError):
            pass
        finally:
            if remote: remote.close()
class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
with Server(('0.0.0.0', 8080), Handler) as server:
    server.serve_forever()
