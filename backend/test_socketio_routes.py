from flask import Flask
from flask_socketio import SocketIO

app = Flask(__name__)

@app.route('/test', methods=['GET'])
def test():
    return 'works'

print("Routes before SocketIO init:")
for rule in app.url_map.iter_rules():
    print(f"  {rule.endpoint}: {rule.rule}")

socketio = SocketIO(app)

print("\nRoutes after SocketIO init:")
for rule in app.url_map.iter_rules():
    print(f"  {rule.endpoint}: {rule.rule}")

print("\nStarting server...")
socketio.run(app, debug=False, host='0.0.0.0', port=5002)
