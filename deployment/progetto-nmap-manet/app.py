from flask import Flask, jsonify, request
import nmap

app = Flask(__name__)
nm = nmap.PortScanner()

@app.route('/scan', methods=['GET'])
def scan_network():
    # The target host is passed as a query parameter (e.g. ?target=10.0.0.1)
    target = request.args.get('target', '127.0.0.1')

    try:
        # Run a fast service-version scan to detect open ports and services
        nm.scan(target, arguments='-F -sV')
    except Exception as e:
        return jsonify({
            "status": {"state": "error"},
            "error": f"nmap scan failed: {e}"
        }), 200  # Return 200 so the caller can parse the JSON

    # If the target is not in the results, the host is unreachable
    if target not in nm.all_hosts():
        return jsonify({
            "status": {"state": "down"},
            "tcp": {},
        })

    return jsonify(nm[target])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
