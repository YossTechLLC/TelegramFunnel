from flask import Flask, request

app = Flask(__name__)

@app.route('/decode_start', methods=['GET', 'POST'])
def decode_start():
    return 'Hello from decode_start!'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
