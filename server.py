#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import urlopen


ROOT_DIR = Path(__file__).resolve().parent
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8001"))
DEFAULT_BUS_API_KEY = "8e57fbd128fc9910c31a1bdab4446063b097b2f59b6f24cdc208abb18fde2ece"
DEFAULT_LOCKER_API_KEY = "c8d7a4c439a6ab3c5c9028a2e513913701fa8caa7c07cfa2e024187e3e8b7d42"
BUS_STOP_API_URL = "https://apis.data.go.kr/1613000/BusSttnInfoInqireService/getCrdntPrxmtSttnList"
BUS_ARRIVAL_API_URL = "https://apis.data.go.kr/1613000/ArvlInfoInqireService/getSttnAcctoArvlPrearngeInfoList"
LOCKER_INFO_API_URL = "https://apis.data.go.kr/B551982/psl_v2/locker_info_v2"
LOCKER_DETAIL_API_URL = "https://apis.data.go.kr/B551982/psl_v2/locker_detail_info_v2"
LOCKER_REALTIME_API_URL = "https://apis.data.go.kr/B551982/psl_v2/locker_realtime_use_v2"


class DemoRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT_DIR), **kwargs)

    def do_GET(self) -> None:
        if self.path == "/health":
            payload = {
                "status": "ok",
                "service": "trip-ui-demo",
                "host": HOST,
                "port": PORT,
            }
            body = json.dumps(payload).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path.startswith("/api/bus/stops"):
            self.handle_bus_stops()
            return

        if self.path.startswith("/api/bus/arrivals"):
            self.handle_bus_arrivals()
            return

        if self.path.startswith("/api/locker/info"):
            self.handle_locker_info()
            return

        if self.path.startswith("/api/locker/detail"):
            self.handle_locker_detail()
            return

        if self.path.startswith("/api/locker/realtime"):
            self.handle_locker_realtime()
            return

        if self.path == "/":
            self.path = "/index.html"

        super().do_GET()

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def get_bus_api_key(self, params: dict[str, list[str]]) -> str:
        return params.get("serviceKey", [os.environ.get("BUS_API_KEY", DEFAULT_BUS_API_KEY)])[0]

    def get_locker_api_key(self, params: dict[str, list[str]]) -> str:
        return params.get("serviceKey", [os.environ.get("LOCKER_API_KEY", DEFAULT_LOCKER_API_KEY)])[0]

    def send_json(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def proxy_public_data(self, upstream_url: str, query_params: dict[str, str]) -> None:
        url = f"{upstream_url}?{urlencode(query_params)}"
        try:
            with urlopen(url, timeout=15) as response:
                body = response.read()
                content_type = response.headers.get("Content-Type", "application/json; charset=utf-8")
                self.send_response(response.status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        except (URLError, PermissionError, OSError):
            body = self.fetch_via_powershell(url)
            if body is None:
                self.send_json(HTTPStatus.BAD_GATEWAY, {"error": "upstream_connection_error", "detail": "failed_to_fetch_upstream"})
                return
            encoded = body.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            self.send_json(HTTPStatus.BAD_GATEWAY, {"error": "upstream_http_error", "status": exc.code, "detail": detail})

    def fetch_via_powershell(self, url: str) -> str | None:
        command = [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "$ProgressPreference='SilentlyContinue'; "
                f"$r=Invoke-WebRequest -Uri '{url}' -UseBasicParsing -TimeoutSec 20; "
                "$r.Content"
            ),
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=False,
                timeout=25,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if completed.returncode != 0:
            return None
        return completed.stdout.decode("utf-8", errors="replace")

    def handle_bus_stops(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        lat = params.get("gpsLati", [""])[0]
        lng = params.get("gpsLong", [""])[0]
        if not lat or not lng:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "missing_coordinates"})
            return
        self.proxy_public_data(
            BUS_STOP_API_URL,
            {
                "serviceKey": self.get_bus_api_key(params),
                "gpsLati": lat,
                "gpsLong": lng,
                "_type": "json",
                "numOfRows": params.get("numOfRows", ["10"])[0],
                "pageNo": params.get("pageNo", ["1"])[0],
            },
        )

    def handle_bus_arrivals(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        city_code = params.get("cityCode", [""])[0]
        node_id = params.get("nodeId", [""])[0]
        if not city_code or not node_id:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "missing_stop_identifiers"})
            return
        self.proxy_public_data(
            BUS_ARRIVAL_API_URL,
            {
                "serviceKey": self.get_bus_api_key(params),
                "cityCode": city_code,
                "nodeId": node_id,
                "_type": "json",
                "numOfRows": params.get("numOfRows", ["10"])[0],
                "pageNo": params.get("pageNo", ["1"])[0],
            },
        )

    def handle_locker_info(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        stdg_cd = params.get("stdgCd", [""])[0]
        if not stdg_cd:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "missing_stdgCd"})
            return
        self.proxy_public_data(
            LOCKER_INFO_API_URL,
            {
                "serviceKey": self.get_locker_api_key(params),
                "stdgCd": stdg_cd,
                "type": params.get("type", ["JSON"])[0],
                "numOfRows": params.get("numOfRows", ["200"])[0],
                "pageNo": params.get("pageNo", ["1"])[0],
            },
        )

    def handle_locker_detail(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        stdg_cd = params.get("stdgCd", [""])[0]
        if not stdg_cd:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "missing_stdgCd"})
            return
        self.proxy_public_data(
            LOCKER_DETAIL_API_URL,
            {
                "serviceKey": self.get_locker_api_key(params),
                "stdgCd": stdg_cd,
                "type": params.get("type", ["JSON"])[0],
                "numOfRows": params.get("numOfRows", ["500"])[0],
                "pageNo": params.get("pageNo", ["1"])[0],
            },
        )

    def handle_locker_realtime(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        stdg_cd = params.get("stdgCd", [""])[0]
        if not stdg_cd:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "missing_stdgCd"})
            return
        self.proxy_public_data(
            LOCKER_REALTIME_API_URL,
            {
                "serviceKey": self.get_locker_api_key(params),
                "stdgCd": stdg_cd,
                "type": params.get("type", ["JSON"])[0],
                "numOfRows": params.get("numOfRows", ["200"])[0],
                "pageNo": params.get("pageNo", ["1"])[0],
            },
        )


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), DemoRequestHandler)
    print(f"Serving {ROOT_DIR} at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
