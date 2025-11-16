#!/usr/bin/env python
import socket
from flask import Flask

class ServerManager:
    def __init__(self):
        self.flask_app = Flask(__name__)
        self.port = None
    
    def find_free_port(self, start_port=5000, max_tries=20):
        """Find a free port for the Flask server."""
        for port in range(start_port, start_port + max_tries):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('localhost', port)) != 0:
                    return port
        raise OSError("No available port found for Flask.")
    
    def start(self):
        """Start the Flask server."""
        self.port = self.find_free_port(5000)
        print(f"🔗 Running Flask on port {self.port}")
        self.flask_app.run(host="0.0.0.0", port=self.port)
    
    def get_app(self):
        """Get the Flask app instance."""
        return self.flask_app