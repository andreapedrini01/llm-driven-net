from flask import Flask, jsonify, request
import nmap

app = Flask(__name__)
nm = nmap.PortScanner()

@app.route('/scan', methods=['GET'])
def scan_network():
    # L'host da scansionare viene passato come parametro (es. ?target=10.0.0.1)
    target = request.args.get('target', '127.0.0.1')

    # Esegue una scansione con script di vulnerabilità per trovare le "falle"
    # chieste dal professore
    nm.scan(target, arguments='-F --script vuln') 

    # Restituisce i dati in formato JSON, pronto per essere letto dalla LLM
    return jsonify(nm[target])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
