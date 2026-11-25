#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
import subprocess
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import urlopen


ROOT_DIR = Path(__file__).resolve().parent


def load_dotenv(path: Path) -> None:
    """`.env` 파일의 KEY=VALUE 줄을 환경변수로 올린다.

    이미 설정된 환경변수는 덮어쓰지 않으므로 셸에서 지정한 값이 우선한다.
    """
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        if name.startswith("export "):
            name = name[len("export "):].strip()
        value = value.strip().strip('"').strip("'")
        if name and name not in os.environ:
            os.environ[name] = value


def env_api_key(*names: str) -> str:
    """설정된 첫 번째 환경변수 값을 돌려준다. 없으면 빈 문자열."""
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


load_dotenv(ROOT_DIR / ".env")

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8001"))
BUS_STOP_API_URL = "https://apis.data.go.kr/1613000/BusSttnInfoInqireService/getCrdntPrxmtSttnList"
BUS_ARRIVAL_API_URL = "https://apis.data.go.kr/1613000/ArvlInfoInqireService/getSttnAcctoArvlPrearngeInfoList"
TOUR_FESTIVAL_API_URL = "https://apis.data.go.kr/B551011/KorService1/searchFestival1"
TOUR_CROWD_API_URL = "https://apis.data.go.kr/B551011/TourismResourceStatsService/getPredictVisitorsInfo"
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

        if self.path.startswith("/api/tour/festivals"):
            self.handle_tour_festivals()
            return

        if self.path.startswith("/api/tour/crowd"):
            self.handle_tour_crowd()
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

    def resolve_api_key(self, params: dict[str, list[str]], *env_names: str) -> str:
        """서버 환경변수 키를 우선 쓰고, 없을 때만 요청의 serviceKey를 쓴다."""
        key = env_api_key(*env_names)
        if key:
            return key
        return params.get("serviceKey", [""])[0].strip()

    def get_bus_api_key(self, params: dict[str, list[str]]) -> str:
        return self.resolve_api_key(params, "BUS_API_KEY", "PUBLIC_DATA_API_KEY")

    def get_tour_api_key(self, params: dict[str, list[str]]) -> str:
        return self.resolve_api_key(params, "TOUR_API_KEY", "PUBLIC_DATA_API_KEY")

    def get_locker_api_key(self, params: dict[str, list[str]]) -> str:
        return self.resolve_api_key(params, "LOCKER_API_KEY", "PUBLIC_DATA_API_KEY")

    def send_json(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def proxy_public_data(self, upstream_url: str, query_params: dict[str, str]) -> None:
        if not query_params.get("serviceKey"):
            self.send_json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {
                    "error": "server_key_not_configured",
                    "detail": (
                        "공공데이터포털 인증키가 설정되지 않았습니다. "
                        ".env 또는 환경변수(TOUR_API_KEY, BUS_API_KEY, LOCKER_API_KEY, "
                        "PUBLIC_DATA_API_KEY)를 설정한 뒤 서버를 다시 시작하세요."
                    ),
                },
            )
            return
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
        except HTTPError as exc:
            # HTTPError는 URLError의 하위 클래스라 먼저 잡아야 업스트림 오류 내용을 그대로 전달할 수 있다.
            detail = exc.read().decode("utf-8", errors="replace")
            self.send_json(HTTPStatus.BAD_GATEWAY, {"error": "upstream_http_error", "status": exc.code, "detail": detail})
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

    def handle_tour_festivals(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        event_date = params.get("eventDate", [""])[0].replace("-", "")
        try:
            selected_date = datetime.strptime(event_date, "%Y%m%d")
        except ValueError:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_event_date"})
            return

        # TourAPI searchFestival1 filters by event start date, so we widen the
        # lookup window a bit and let the client keep only the relevant entries.
        event_start_date = (selected_date - timedelta(days=30)).strftime("%Y%m%d")

        self.proxy_public_data(
            TOUR_FESTIVAL_API_URL,
            {
                "serviceKey": self.get_tour_api_key(params),
                "MobileOS": "ETC",
                "MobileApp": "EcoTravel",
                "_type": "json",
                "listYN": "Y",
                "arrange": params.get("arrange", ["A"])[0],
                "numOfRows": params.get("numOfRows", ["200"])[0],
                "pageNo": params.get("pageNo", ["1"])[0],
                "areaCode": params.get("areaCode", ["38"])[0],
                "eventStartDate": params.get("eventStartDate", [event_start_date])[0],
            },
        )

    def handle_tour_crowd(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        ym = params.get("YM", [""])[0].strip()
        if len(ym) != 6 or not ym.isdigit():
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_ym"})
            return
        self.proxy_public_data(
            TOUR_CROWD_API_URL,
            {
                "serviceKey": self.get_tour_api_key(params),
                "YM": ym,
                "SIDO": params.get("SIDO", ["전라남도"])[0],
                "MobileOS": "ETC",
                "MobileApp": "EcoTravel",
                "_type": "json",
                "numOfRows": params.get("numOfRows", ["20"])[0],
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
