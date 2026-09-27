from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return '<h1>Smart Campus Hub</h1><p>Flask is working! Member 1 setup complete.</p>'

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)