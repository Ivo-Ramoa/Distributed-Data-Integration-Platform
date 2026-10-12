import os
import json
import grpc
import requests
from concurrent import futures

import ativos_pb2
import ativos_pb2_grpc

XML_SERVICE_BASE = os.getenv("XML_SERVICE_BASE", "http://xml-service:3000")
GRPC_PORT = int(os.getenv("GRPC_PORT", "50051"))

def get_json(path: str, params=None):
    url = f"{XML_SERVICE_BASE}{path}"
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()

class Tp3Service(ativos_pb2_grpc.Tp3ServiceServicer):
    def Ping(self, request, context):
        return ativos_pb2.Empty()

    def GetAtivos(self, request, context):
        data = get_json("/query/ativos")
        rows = data.get("ativos", [])
        resp = ativos_pb2.AtivosResponse()
        for x in rows:
            resp.ativos.append(
                ativos_pb2.Ativo(
                    ticker=str(x.get("ticker", "")),
                    tipo=str(x.get("tipo", "")),
                    preco=float(x.get("preco", 0) or 0),
                    volume=int(x.get("volume", 0) or 0),
                )
            )
        return resp

    def GetAggCategory(self, request, context):
        data = get_json("/query/agg/category")
        rows = data.get("agg", [])
        resp = ativos_pb2.AggResponse()
        for x in rows:
            resp.agg.append(
                ativos_pb2.AggItem(
                    tipo=str(x.get("tipo", "")),
                    total=int(x.get("total", 0) or 0),
                )
            )
        return resp

    def GetTopVolume(self, request, context):
        limit = int(request.limit or 5)
        data = get_json("/query/top-volume", params={"limit": limit})
        rows = data.get("top", [])
        resp = ativos_pb2.TopResponse()
        for x in rows:
            resp.top.append(
                ativos_pb2.Ativo(
                    ticker=str(x.get("ticker", "")),
                    tipo=str(x.get("tipo", "")),
                    preco=0.0,
                    volume=int(x.get("volume", 0) or 0),
                )
            )
        return resp

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    ativos_pb2_grpc.add_Tp3ServiceServicer_to_server(Tp3Service(), server)
    server.add_insecure_port(f"0.0.0.0:{GRPC_PORT}")
    server.start()
    print(f"grpc-service on :{GRPC_PORT}")
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
