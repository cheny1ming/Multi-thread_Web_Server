# Multi-thread Web Server - COMP2322
## How to Compile & Run
1. Environment: Python 3.6+
2. Steps:
   - Create "www" folder in the same directory
   - Place web files into "www"
   - Run: python server.py
3. Test URL: http://127.0.0.1:8080

## Functions
- Multi-threaded concurrent processing
- Support GET/HEAD methods
- Support text/html, image/jpeg/png, etc.
- 5 HTTP status codes: 200,304,400,403,404
- Persistent/non-persistent connection
- Cache control with Last-Modified
- Request log recording