import os
import requests
from xmlrpc.server import SimpleXMLRPCServer

XML_SERVICE_BASE = os.getenv("XML_SERVICE_BASE", "http://xml-service:3000")
PORT = int(os.getenv("XMLRPC_PORT", "9001"))

def ping():
    return "pong"

def agg_category():
    r = requests.get(f"{XML_SERVICE_BASE}/query/agg/category", timeout=15)
    r.raise_for_status()
    return r.json()  # retorna dict (XML-RPC suporta structs)

def top_volume(limit=5):
    r = requests.get(f"{XML_SERVICE_BASE}/query/top-volume", params={"limit": int(limit)}, timeout=15)
    r.raise_for_status()
    return r.json()

if __name__ == "__main__":
    server = SimpleXMLRPCServer(("0.0.0.0", PORT), allow_none=True)
    server.register_function(ping, "ping")
    server.register_function(agg_category, "agg_category")
    server.register_function(top_volume, "top_volume")
    print(f"xmlrpc-service on :{PORT}", flush=True)
    server.serve_forever()
