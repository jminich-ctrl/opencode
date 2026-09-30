#!/usr/bin/env python3
"""Proxy que mide el peso del harness: qué manda OpenCode en cada request.

Se pone entre OpenCode y ColabHive, registra el tamaño y la forma del pedido, y
reenvía sin tocar nada. Sirve para contestar lo que ninguna doc contesta: cuántos
caracteres de system prompt, cuántas herramientas y cuánto historial viaja en cada
paso de un agente.

  python3 scripts/proxy_medidor.py &            # escucha en 8899
  ... apuntar baseURL a http://127.0.0.1:8899/v1 ...
  cat research/live/harness.jsonl               # una línea por request
"""
import http.server, json, os, pathlib, socketserver, sys, urllib.request

DESTINO = "https://api.colabhive.com/v1"
REGISTRO = pathlib.Path(os.path.expanduser("~/colabhive-opencode/research/live/harness.jsonl"))
REGISTRO.parent.mkdir(parents=True, exist_ok=True)


class Proxy(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):            # silencio: el registro va al jsonl
        pass

    def do_POST(self):
        largo = int(self.headers.get("Content-Length", 0))
        cuerpo = self.rfile.read(largo)
        try:
            d = json.loads(cuerpo)
            msgs = d.get("messages", [])
            def texto(m):
                c = m.get("content")
                if isinstance(c, str):
                    return c
                if isinstance(c, list):
                    return "".join(p.get("text", "") for p in c if isinstance(p, dict))
                return ""
            sistema = sum(len(texto(m)) for m in msgs if m.get("role") == "system")
            usuario = sum(len(texto(m)) for m in msgs if m.get("role") == "user")
            asistente = sum(len(texto(m)) for m in msgs if m.get("role") == "assistant")
            herramientas = d.get("tools") or []
            entrada = {
                "modelo": d.get("model", "")[:8],
                "mensajes": len(msgs),
                "chars_system": sistema,
                "chars_user": usuario,
                "chars_assistant": asistente,
                "chars_total": len(cuerpo),
                "herramientas": len(herramientas),
                "chars_herramientas": len(json.dumps(herramientas)),
                "nombres_herramientas": [h.get("function", {}).get("name") for h in herramientas],
            }
            with REGISTRO.open("a") as f:
                f.write(json.dumps(entrada, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"(no pude leer el cuerpo: {e})", file=sys.stderr)

        destino = DESTINO + self.path.replace("/v1", "", 1)
        cabeceras = {k: v for k, v in self.headers.items()
                     if k.lower() not in ("host", "content-length", "connection")}
        req = urllib.request.Request(destino, data=cuerpo, headers=cabeceras, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=1800) as r:
                self.send_response(r.status)
                for k, v in r.headers.items():
                    if k.lower() not in ("transfer-encoding", "connection", "content-length"):
                        self.send_header(k, v)
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                while True:
                    trozo = r.read(4096)
                    if not trozo:
                        break
                    self.wfile.write(b"%x\r\n%s\r\n" % (len(trozo), trozo))
                    self.wfile.flush()
                self.wfile.write(b"0\r\n\r\n")
        except urllib.error.HTTPError as e:
            datos = e.read()
            self.send_response(e.code)
            self.send_header("Content-Length", str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)

    def do_GET(self):
        destino = DESTINO + self.path.replace("/v1", "", 1)
        cabeceras = {k: v for k, v in self.headers.items() if k.lower() not in ("host", "connection")}
        try:
            with urllib.request.urlopen(urllib.request.Request(destino, headers=cabeceras), timeout=60) as r:
                datos = r.read()
                self.send_response(r.status)
                self.send_header("Content-Type", r.headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(datos)))
                self.end_headers()
                self.wfile.write(datos)
        except urllib.error.HTTPError as e:
            datos = e.read()
            self.send_response(e.code)
            self.send_header("Content-Length", str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)


class Servidor(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
    print(f"proxy midiendo en http://127.0.0.1:{puerto}/v1 -> {DESTINO}")
    Servidor(("127.0.0.1", puerto), Proxy).serve_forever()
