from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/test', methods=['GET'])
def test():
    return jsonify({"message": "Test endpoint works!"})

@app.route('/auth/demo-token', methods=['GET'])
def demo_token():
    return jsonify({"message": "Demo token endpoint works!"})

if __name__ == "__main__":
    print("=" * 60)
    print("ROUTES REGISTERED:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule.endpoint}: {rule.rule} -> {rule.methods}")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=5001)
