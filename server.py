# Import required standard libraries
import socket
import threading
import os
import datetime
from datetime import timedelta, timezone
import mimetypes

# Note: Using threading.Thread directly instead of ThreadPoolExecutor for better Ctrl+C handling on Windows

# -------------------------- Server Configuration --------------------------
BEIJING_TZ = timezone(timedelta(hours=8))
HOST = '127.0.0.1'
PORT = 8080
BUFFER_SIZE = 4096
WEB_ROOT = './www'
LOG_FILE = 'server_log.txt'
SUPPORTED_METHODS = ['GET', 'HEAD']
HTTP_VER = 'HTTP/1.1'
MAX_THREADS = 20
SOCKET_TIMEOUT = 1  # Socket timeout in seconds for KeyboardInterrupt detection

if not os.path.exists(WEB_ROOT):
    os.makedirs(WEB_ROOT)

# Thread-safe lock for log file writing
log_lock = threading.Lock()

# ----------------------------- Core Functions -----------------------------
def write_log(client_ip, access_time, req_file, status_code):
    """
    Write request log to log file (thread-safe)
    Args:
        client_ip: Client IP address
        access_time: Time when request is received
        req_file: Requested file path
        status_code: HTTP response status code
    """
    with log_lock:
        with open(LOG_FILE, 'a', encoding='utf-8') as log_fp:
            log_line = f"{client_ip} | {access_time} | {req_file} | {status_code}\n"
            log_fp.write(log_line)

def get_file_last_modified(file_path):
    """
    Get file last-modified time in HTTP standard format
    Args:
        file_path: Local file path
    Returns:
        Formatted time string (Beijing Time)
    """
    mod_timestamp = os.path.getmtime(file_path)
    mod_time = datetime.datetime.fromtimestamp(mod_timestamp, BEIJING_TZ)
    return mod_time.strftime('%a, %d %b %Y %H:%M:%S CST')  # CST = China Standard Time

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

def build_http_response(status, headers, body=b'', show_output=True):
    """
    Build complete HTTP response message
    Args:
        status: HTTP status code
        headers: Response header dict
        body: Response body bytes
        show_output: Whether to print response headers (default True)
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

    # Add Date header (HTTP/1.1 required)
    # Using Beijing Time (CST = China Standard Time)
    date_str = datetime.datetime.now(BEIJING_TZ).strftime('%a, %d %b %Y %H:%M:%S CST')
    headers['Date'] = date_str

    # Add Server header
    headers['Server'] = 'TEST Server'

    # Status line
    status_line = f"{HTTP_VER} {status} {status_msg[status]}"
    res = f"{status_line}\r\n"

    # Headers
    for k, v in headers.items():
        res += f"{k}: {v}\r\n"
    res += "\r\n"

    # Print response headers if requested
    if show_output:
        print(f"[Response Headers]", flush=True)
        print(f" {status_line}", flush=True)
        for k, v in headers.items():
            print(f" {k}: {v}", flush=True)
        body_preview = body[:100] if body else b'(empty)'
        if isinstance(body_preview, bytes):
            try:
                body_preview = body_preview.decode('utf-8', errors='replace')
            except:
                body_preview = f'<binary data, {len(body)} bytes>'
        print(f"[Body] {body_preview if len(body) <= 100 else f'<{len(body)} bytes>'}\n", flush=True)

    return res.encode('utf-8') + body

def handle_client(client_sock, client_addr):
    """
    Handle one client connection in one thread
    Args:
        client_sock: Client connection socket
        client_addr: Client (IP, port)
    """
    client_ip = client_addr[0]
    client_port = client_addr[1]
    keep_alive = False

    # Set socket timeout to avoid blocking forever
    client_sock.settimeout(30)  # 30 second timeout

    print(f"[Client] Connected from {client_ip}:{client_port}", flush=True)

    try:
        while True:
            # Receive request data
            try:
                raw_req = client_sock.recv(BUFFER_SIZE)
            except socket.timeout:
                print(f"[Timeout] Client {client_ip}:{client_port} - no data for 30s", flush=True)
                break
            except:
                break
            if not raw_req:
                break

            # Parse request
            method, path, proto, headers = parse_http_request(raw_req)
            access_time = datetime.datetime.now(BEIJING_TZ).strftime('%Y-%m-%d %H:%M:%S')

            # Print request details
            print(f"[Request] {method} {path} {proto} from {client_ip}:{client_port}", flush=True)

            # Default page
            if path == '/':
                path = '/index.html'
            local_path = WEB_ROOT + path

            print(f"[Path] Mapped to: {local_path}", flush=True)

            # -------------------------- Error Handling --------------------------
            # 400 Bad Request: invalid method or request
            if not method or method not in SUPPORTED_METHODS:
                print(f"[Error] 400 Bad Request - Invalid method: {method}", flush=True)
                resp = build_http_response(400, {'Content-Length': 0})
                client_sock.sendall(resp)
                write_log(client_ip, access_time, path, 400)
                break
            # 403 Forbidden: path traversal attack
            if '..' in path:
                print(f"[Error] 403 Forbidden - Path traversal attempt detected", flush=True)
                resp = build_http_response(403, {'Content-Length': 0})
                client_sock.sendall(resp)
                write_log(client_ip, access_time, path, 403)
                break
            # 404 Not Found: file does not exist
            if not os.path.isfile(local_path):
                print(f"[Error] 404 Not Found - File: {local_path}", flush=True)
                resp = build_http_response(404, {'Content-Length': 0})
                client_sock.sendall(resp)
                write_log(client_ip, access_time, path, 404)
                break

            # -------------------------- Cache Control (304) --------------------------
            file_mod_time = get_file_last_modified(local_path)
            if 'If-Modified-Since' in headers:
                print(f"[Cache] Client has cached version (If-Modified-Since: {headers['If-Modified-Since']})", flush=True)
                print(f"[Cache] Current file time: {file_mod_time}", flush=True)
                if headers['If-Modified-Since'] == file_mod_time:
                    print(f"[Cache] 304 Not Modified - Using cache", flush=True)
                    resp_headers = {'Last-Modified': file_mod_time}
                    resp = build_http_response(304, resp_headers)
                    client_sock.sendall(resp)
                    write_log(client_ip, access_time, path, 304)
                    break

            # -------------------------- Normal Response (200) --------------------------
            file_size = os.path.getsize(local_path)
            mime_type = mimetypes.guess_type(local_path)[0] or 'application/octet-stream'
            print(f"[File] Size: {file_size} bytes, Type: {mime_type}", flush=True)
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
            # HEAD method only returns headers, no body (HTTP/1.1 specification)
            body = b''
            if method == 'GET':
                with open(local_path, 'rb') as fp:
                    body = fp.read()

            # Send response (build_http_response will print headers)
            resp = build_http_response(200, resp_headers, body)
            client_sock.sendall(resp)
            write_log(client_ip, access_time, path, 200)

            # Close if not persistent connection
            if not keep_alive:
                print(f"[Connection] Closing connection (Connection: {conn_type})", flush=True)
                break
            else:
                print(f"[Connection] Keeping connection alive (keep-alive)", flush=True)

    except Exception as e:
        print(f"[Error] Handle client {client_addr}: {str(e)}", flush=True)
    finally:
        client_sock.close()
        print(f"[Client] Disconnected {client_ip}:{client_port}\n", flush=True)

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
        print(f"[Hint] Port {PORT} may already be in use.")
        return
    server_sock.listen(5)

    print(f"[INFO] Server runs on URL: http://{HOST}:{PORT}", flush=True)
    print("Waiting for connections... (Press Ctrl+C to stop)\n", flush=True)

    server_sock.settimeout(1)  # Set timeout for KeyboardInterrupt detection

    try:
        while True:
            try:
                client_sock, client_addr = server_sock.accept()
                print(f"[Connection] Accepted from {client_addr[0]}:{client_addr[1]}", flush=True)

                # Create daemon thread to handle client
                # Daemon threads will be killed when main program exits
                client_thread = threading.Thread(
                    target=handle_client,
                    args=(client_sock, client_addr),
                    daemon=True,
                    name=f"client-{client_addr[0]}:{client_addr[1]}"
                )
                client_thread.start()

                # Optionally limit active threads
                active_threads = threading.active_count() - 1  # Exclude main thread
                if active_threads >= MAX_THREADS:
                    print(f"[WARN] Thread limit reached ({active_threads} active)", flush=True)

            except socket.timeout:
                # Timeout is expected, continue loop to check for KeyboardInterrupt
                continue

    except KeyboardInterrupt:
        print("\n[INFO] Server stopped by user.")
    finally:
        server_sock.close()
        print("[INFO] Server socket closed.")
        print("[INFO] All daemon threads will exit automatically.")

if __name__ == "__main__":
    server()