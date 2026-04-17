# Multi-thread Web Server - COMP2322

This is a repository of a multi-threaded HTTP/1.1 web server implemented in Python with support for concurrent connections, caching, and comprehensive request logging.

## Functions
- Multi-threaded concurrent processing (supports up to 20 simultaneous connections)
- Support GET/HEAD methods
- Support text/html, image/jpeg/png, etc.
- 5 HTTP status codes: 200, 304, 400, 403, 404
- Persistent/non-persistent connection (via Connection: keep-alive header)
- Cache control with Last-Modified (supports 304 Not Modified responses)
- Request log recording to file

## Project Structure

```
Multi-thread Web Server/
├── server.py           # Main server implementation
├── www/                # Web root directory
│   ├── index.html      # Default homepage
│   ├── test.txt        # Test text file
│   └── test.png        # Test image file
├── server_log.txt      # Request log file (auto-generated)
└── README.md           # This file
```

## How to Compile & Run?

This project uses pure Python and only internal libraries will be used in this project. 

### Prerequisites
- Python 3.6 or higher
- No external library required!

### Running the Server

```bash
python server.py
```

The server will start on `http://127.0.0.1:8080` by default.

The URL `http://127.0.0.1:8080` can be visited on browser.

Press `Ctrl+C` to stop the server.

### Configuration

You can modify these constants in `server.py`:
- `HOST` - Server IP address (default: `127.0.0.1`)
- `PORT` - Server port (default: `8080`)
- `WEB_ROOT` - Web root directory (default: `./www`)
- `MAX_THREADS` - Maximum concurrent threads (default: `20`)
- `LOG_FILE` - Log file path (default: `server_log.txt`)

## Testing

**Before testing:**
Make sure that the server is running at `127.0.0.1:8080`

### Test GET/HEAD Methods

**Using curl:**

```bash
# GET request for HTML
curl -v http://127.0.0.1:8080/index.html

# GET request for default page
curl -v http://127.0.0.1:8080/

# HEAD request
curl -I http://127.0.0.1:8080/index.html
```

The `curl` command is non-persistent connection by default. We test persistent test by:
```bash
# Persistent connection test
curl -v --header "Connection: keep-alive" http://127.0.0.1:8080/index.html
```

**Using browser:**
- Navigate to `http://127.0.0.1:8080/`

### Test Text and Image

The `www/` directory contains test files:

1. **Text File (`test.txt`)**
   ```bash
   curl http://127.0.0.1:8080/test.txt
   ```

2. **Image File (`test.png`)**
   ```bash
   curl -o downloaded_image.png http://127.0.0.1:8080/test.png
   # Or view in browser: http://127.0.0.1:8080/test.png
   ```

3. **HTML Page (`index.html`)**
   - Contains embedded test image
   - Access at `http://127.0.0.1:8080/` or `http://127.0.0.1:8080/index.html`

### Cache Testing

Test the 304 Not Modified response:

```bash
# First request - will return 200
curl -v http://127.0.0.1:8080/index.html

# Second request with If-Modified-Since - will return 304
curl -v --header "If-Modified-Since: Wed, 16 Apr 2025 12:00:00 CST" http://127.0.0.1:8080/index.html
```

## Log Format

All HTTP requests are logged to `server_log.txt` with the following format:

```
{Client_IP} | {Access_Time} | {Requested_File} | {Status_Code}
```

### Example Log Entry:

```
127.0.0.1 | 2025-04-17 14:30:25 | /index.html | 200
127.0.0.1 | 2025-04-17 14:30:26 | /test.png | 200
127.0.0.1 | 2025-04-17 14:30:27 | /nonexistent.html | 404
127.0.0.1 | 2025-04-17 14:30:28 | /../../etc/passwd | 403
```

### Log Fields:
- **Client_IP**: IP address of the client making the request
- **Access_Time**: Timestamp in Beijing Time (CST) - Format: `YYYY-MM-DD HH:MM:SS`
- **Requested_File**: The requested URL path
- **Status_Code**: HTTP response status code (200, 304, 400, 403, 404)