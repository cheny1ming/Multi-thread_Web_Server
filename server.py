# Import required standard libraries
import socket
import threading
import os
import datetime
import mimetypes
from concurrent.futures import ThreadPoolExecutor

# -------------------------- Server Configuration --------------------------
HOST = '127.0.0.1'
PORT = 8080
BUFFER_SIZE = 4096
WEB_ROOT = './www'
LOG_FILE = 'server_log.txt'
SUPPORTED_METHODS = ['GET', 'HEAD']
HTTP_VER = 'HTTP/1.1'
MAX_THREADS = 20

if not os.path.exists(WEB_ROOT):
    os.makedirs(WEB_ROOT)

# ----------------------------- Core Functions -----------------------------
def write_log(client_ip, access_time, req_file, status_code):
    """
    Write request log to log file
    Args:
        client_ip: Client IP address
        access_time: Time when request is received
        req_file: Requested file path
        status_code: HTTP response status code
    """
    with open(LOG_FILE, 'a', encoding='utf-8') as log_fp:
        log_line = f"{client_ip} | {access_time} | {req_file} | {status_code}\n"
        log_fp.write(log_line)

def get_file_last_modified(file_path):
    """
    Get file last-modified time in HTTP standard format
    Args:
        file_path: Local file path
    Returns:
        Formatted time string (GMT)
    """
    mod_timestamp = os.path.getmtime(file_path)
    mod_time = datetime.datetime.fromtimestamp(mod_timestamp, datetime.UTC)
    return mod_time.strftime('%a, %d %b %Y %H:%M:%S GMT')

def parse_http_request(raw_data):
    """
    Parse raw HTTP request data
    Args:
        raw_data: Bytes data received from client
    Returns:
        method, path, protocol, headers (None if invalid)
    """
    try:
        req_str = raw_data.decode('utf-8', errors='ignore')
        req_lines = req_str.split('\r\n')
        # Parse request line
        first_line = req_lines[0].split()
        if len(first_line) < 3:
            return None, None, None, {}
        method, path, protocol = first_line
        # Parse request headers
        headers = {}
        for line in req_lines[1:]:
            if ': ' in line:
                key, val = line.split(': ', 1)
                headers[key.strip()] = val.strip()
        return method, path, protocol, headers
    except Exception:
        return None, None, None, {}

def build_http_response(status, headers, body=b''):
    """
    Build complete HTTP response message
    Args:
        status: HTTP status code
        headers: Response header dict
        body: Response body bytes
    Returns:
        Complete HTTP response bytes
    """
    status_msg = {
        200: 'OK',
        304: 'Not Modified',
        400: 'Bad Request',
        403: 'Forbidden',
        404: 'Not Found'
    }
    # Status line
    res = f"{HTTP_VER} {status} {status_msg[status]}\r\n"
    # Headers
    for k, v in headers.items():
        res += f"{k}: {v}\r\n"
    res += "\r\n"
    return res.encode('utf-8') + body

def handle_client(client_sock, client_addr):
    """
    Handle one client connection in one thread
    Args:
        client_sock: Client connection socket
        client_addr: Client (IP, port)
    """
    client_ip = client_addr[0]
    keep_alive = False

    try:
        while True:
            # Receive request data
            raw_req = client_sock.recv(BUFFER_SIZE)
            if not raw_req:
                break

            # Parse request
            method, path, proto, headers = parse_http_request(raw_req)
            access_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            # Default page
            if path == '/':
                path = '/index.html'
            local_path = WEB_ROOT + path

            # -------------------------- Error Handling --------------------------
            # 400 Bad Request: invalid method or request
            if not method or method not in SUPPORTED_METHODS:
                resp = build_http_response(400, {'Content-Length': 0})
                client_sock.sendall(resp)
                write_log(client_ip, access_time, path, 400)
                break
            # 403 Forbidden: path traversal attack
            if '..' in path:
                resp = build_http_response(403, {'Content-Length': 0})
                client_sock.sendall(resp)
                write_log(client_ip, access_time, path, 403)
                break
            # 404 Not Found: file does not exist
            if not os.path.isfile(local_path):
                resp = build_http_response(404, {'Content-Length': 0})
                client_sock.sendall(resp)
                write_log(client_ip, access_time, path, 404)
                break

            # -------------------------- Cache Control (304) --------------------------
            file_mod_time = get_file_last_modified(local_path)
            if 'If-Modified-Since' in headers:
                if headers['If-Modified-Since'] == file_mod_time:
                    resp_headers = {'Last-Modified': file_mod_time}
                    resp = build_http_response(304, resp_headers)
                    client_sock.sendall(resp)
                    write_log(client_ip, access_time, path, 304)
                    break

            # -------------------------- Normal Response (200) --------------------------
            file_size = os.path.getsize(local_path)
            mime_type = mimetypes.guess_type(local_path)[0] or 'application/octet-stream'
            # Connection header: keep-alive / close
            conn_type = headers.get('Connection', 'close')
            keep_alive = conn_type.lower() == 'keep-alive'

            resp_headers = {
                'Content-Type': mime_type,
                'Content-Length': file_size,
                'Last-Modified': file_mod_time,
                'Connection': conn_type
            }

            # Read file content only for GET
            body = b''
            if method == 'GET':
                with open(local_path, 'rb') as fp:
                    body = fp.read()

            # Send response
            resp = build_http_response(200, resp_headers, body)
            client_sock.sendall(resp)
            write_log(client_ip, access_time, path, 200)

            # Close if not persistent connection
            if not keep_alive:
                break

    except Exception as e:
        print(f"[Error] Handle client {client_addr}: {str(e)}")
    finally:
        client_sock.close()

def server():
    """Start multi-threaded web server"""
    # Create TCP socket
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Allow port reuse
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # Bind and listen
    try:
        server_sock.bind((HOST, PORT))
    except OSError as e:
        print(f"[Error] Failed to bind to {HOST}:{PORT}")
        print(f"[Error] {e}")
        print(f"[Hint] Port {PORT} may already be in use. Try:")
        print(f"       1. Close other programs using port {PORT}")
        print(f"       2. Or change the PORT variable in the code")
        return
    server_sock.listen(5)
    print(f"✅ Server running at http://{HOST}:{PORT}")

    with ThreadPoolExecutor(MAX_THREADS) as executor:
        try:
            while True:
                client_sock, client_addr = server_sock.accept()
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] New connection from {client_addr[0]}:{client_addr[1]}", flush=True)
                # Submit task to thread pool
                executor.submit(handle_client, client_sock, client_addr)
        except KeyboardInterrupt:
            print("\nServer stopped by user")
        finally:
            server_sock.close()

if __name__ == "__main__":
    server()