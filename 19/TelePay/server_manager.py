#!/usr/bin/env python
import socket
from flask import Flask

class ServerManager:
    def __init__(self):
        self.flask_app = Flask(__name__)
        self.port = None
    
    def find_free_port(self, start_port=5000, max_tries=1000):
        """Find a free port for the Flask server."""
        # First try the specified range
        for port in range(start_port, start_port + max_tries):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(('localhost', port))
                    return port
                except OSError:
                    continue
        
        # Fallback: let OS assign an available port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('localhost', 0))  # 0 means OS will assign available port
                port = s.getsockname()[1]
                return port
            except OSError as e:
                raise OSError(f"No available port found for Flask after trying {max_tries} ports and OS assignment: {e}")
    
    def start(self):
        """Start the Flask server."""
        self.port = self.find_free_port(5000)
        print(f"Running Flask on port {self.port}")
        self.flask_app.run(host="0.0.0.0", port=self.port)
    
    def get_app(self):
        """Get the Flask app instance."""
        return self.flask_app