import os
import threading
import http.server
import socketserver
from decentralized_worker import main as worker_main
import sys

# Define a simple handler to satisfy Render's web service requirement
class HealthCheckHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"OBLIVION Worker is running!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    print(f"🌍 Starting dummy web server on port {port}")
    with socketserver.TCPServer(("", port), HealthCheckHandler) as httpd:
        httpd.serve_forever()

def run_worker():
    print("👷 Starting worker process based on existing code...")
    # Simulate command line arguments if needed, or just call main
    # We call main() which parses args. We can inject args via sys.argv if needed.
    sys.argv = ["decentralized_worker.py", "run"]
    try:
        worker_main()
    except Exception as e:
        print(f"❌ Worker crashed: {e}")

if __name__ == "__main__":
    # Start worker in a separate thread
    worker_thread = threading.Thread(target=run_worker, daemon=True)
    worker_thread.start()
    
    # Run web server in main thread (blocking, to keep container alive)
    run_web_server()
