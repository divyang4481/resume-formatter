import socket
import sys

host = "agentic-platform-db-dev.ctgoo20ag6cj.ap-south-1.rds.amazonaws.com"
port = 5432

print(f"Testing TCP connection to {host}:{port}...")
try:
    s = socket.create_connection((host, port), timeout=5)
    print("SUCCESS: Connected to database port!")
    s.close()
except Exception as e:
    print(f"FAILED: Could not connect to database port: {e}")
    sys.exit(1)
