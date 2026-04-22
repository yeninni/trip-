#!/usr/bin/env python3
from __future__ import annotations

import json
import os
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
BUS_STOP_API_URL = "https://apis.data.go.kr/1613000/BusSttnInfoInqireService/getCrdntPrxmtSttnList"
BUS_ARRIVAL_API_URL = "https://apis.data.go.kr/1613000/ArvlInfoInqireService/getSttnAcctoArvlPrearngeInfoList"
LOCKER_API_BASE_URL = "https://apis.data.go.kr/B551982/psl_v2"
LOCKER_INFO_API_URL = f"{LOCKER_API_BASE_URL}/locker_info_v2"
LOCKER_DETAIL_API_URL = f"{LOCKER_API_BASE_URL}/locker_detail_info_v2"
LOCKER_REALTIME_API_URL = f"{LOCKER_API_BASE_URL}/locker_realtime_use_v2"
TOUR_API_BASE_URL = "https://apis.data.go.kr/B551011/KorService1"
FESTIVAL_SEARCH_API_URL = f"{TOUR_API_BASE_URL}/searchFestival1"
FESTIVAL_AREA_API_URL = f"{TOUR_API_BASE_URL}/areaBasedList1"


def ensure_list(value: object) -> list[dict]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def to_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def to_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def pick_first_int(source: dict, candidate_keys: tuple[str, ...]) -> int | None:
    lowered = {str(key).lower(): value for key, value in source.items()}
    for candidate in candidate_keys:
        for key, value in lowered.items():
            if candidate in key:
                parsed = to_int(value)
                if parsed is not None:
                    return parsed
    return None


def extract_realtime_stats(item: dict) -> dict[str, int | None]:
    return {
        "avail": pick_first_int(item, ("usepsbl", "psbl", "avail", "free", "empty")),
        "total": pick_first_int(item, ("total", "all", "sum", "cnt")),
        "used": pick_first_int(item, ("used", "use", "occup", "busy")),
    }


def normalize_lockers(info_payload: dict, detail_payload: dict, realtime_payload: dict | None) -> dict:
    info_items = ensure_list(info_payload.get("body", {}).get("item"))
    detail_items = ensure_list(detail_payload.get("body", {}).get("item"))
    realtime_items = ensure_list((realtime_payload or {}).get("body", {}).get("item"))

    detail_counts: dict[str, int] = {}
    detail_names: dict[str, str] = {}
    for item in detail_items:
        locker_id = str(item.get("stlckId", "")).strip()
        if not locker_id:
            continue
        detail_counts[locker_id] = detail_counts.get(locker_id, 0) + 1
        if item.get("stlckNm"):
            detail_names[locker_id] = str(item["stlckNm"]).strip()

    realtime_by_id: dict[str, dict[str, int | None]] = {}
    for item in realtime_items:
        locker_id = str(item.get("stlckId", "")).strip()
        if locker_id:
            realtime_by_id[locker_id] = extract_realtime_stats(item)

    normalized_items: list[dict] = []
    for item in info_items:
        locker_id = str(item.get("stlckId", "")).strip()
        if not locker_id:
            continue

        realtime_stats = realtime_by_id.get(locker_id, {})
        total = detail_counts.get(locker_id) or to_int(item.get("stlckCnt"))
        realtime_total = realtime_stats.get("total")
        if realtime_total is not None:
            total = max(total or 0, realtime_total)

        avail = realtime_stats.get("avail")
        used = realtime_stats.get("used")
        if avail is None and used is not None and total is not None:
            avail = max(total - used, 0)
        if avail is not None and total is not None:
            avail = max(min(avail, total), 0)

        normalized_items.append(
            {
                "id": locker_id,
                "n": detail_names.get(locker_id) or item.get("stlckRprsPstnNm") or "공영 물품보관함",
                "addr": item.get("fcltRoadNmAddr") or item.get("fcltLotnoAddr") or "",
                "avail": avail,
                "total": total,
                "lat": to_float(item.get("lat")),
                "lng": to_float(item.get("lot")),
                "location": item.get("stlckDtlPstnNm") or item.get("stlckRprsPstnNm") or "",
                "manager": item.get("mngInstNm") or "",
                "phone": item.get("custCntrTelno") or item.get("mngInstTelno") or "",
                "realtimeAvailable": avail is not None,
                "source": "public_data",
            }
        )

    return {
        "items": normalized_items,
        "meta": {
            "infoCount": len(info_items),
            "detailCount": len(detail_items),
            "realtimeCount": len(realtime_items),
            "realtimeAvailable": any(item["realtimeAvailable"] for item in normalized_items),
        },
    }


def normalize_festivals(payload: dict, source: str) -> dict:
    items = ensure_list(payload.get("response", {}).get("body", {}).get("items", {}).get("item"))
    normalized_items: list[dict] = []
    for item in items:
        normalized_items.append(
            {
                "id": str(item.get("contentid", "")).strip(),
                "title": item.get("title") or "",
                "addr1": item.get("addr1") or "",
                "addr2": item.get("addr2") or "",
                "eventStartDate": item.get("eventstartdate") or "",
                "eventEndDate": item.get("eventenddate") or "",
                "tel": item.get("tel") or "",
                "mapx": to_float(item.get("mapx")),
                "mapy": to_float(item.get("mapy")),
                "firstimage": item.get("firstimage") or "",
                "areacode": item.get("areacode") or "",
                "sigungucode": item.get("sigungucode") or "",
                "cat2": item.get("cat2") or "",
                "cat3": item.get("cat3") or "",
                "source": source,
            }
        )
    return {
        "items": normalized_items,
        "meta": {
            "count": len(normalized_items),
            "source": source,
        },
    }


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

        if self.path.startswith("/api/lockers"):
            self.handle_lockers()
            return

        if self.path.startswith("/api/festivals"):
            self.handle_festivals()
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

    def get_public_api_key(self, params: dict[str, list[str]]) -> str:
        return params.get("serviceKey", [os.environ.get("PUBLIC_DATA_API_KEY", DEFAULT_BUS_API_KEY)])[0]

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
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            self.send_json(HTTPStatus.BAD_GATEWAY, {"error": "upstream_http_error", "status": exc.code, "detail": detail})
        except URLError as exc:
            self.send_json(HTTPStatus.BAD_GATEWAY, {"error": "upstream_connection_error", "detail": str(exc.reason)})

    def fetch_json(self, upstream_url: str, query_params: dict[str, str]) -> dict:
        url = f"{upstream_url}?{urlencode(query_params)}"
        with urlopen(url, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))

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

    def handle_lockers(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        stdg_cd = params.get("stdgCd", [""])[0]
        if not stdg_cd:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "missing_stdgCd"})
            return

        query = {
            "serviceKey": self.get_public_api_key(params),
            "stdgCd": stdg_cd,
            "type": params.get("type", ["JSON"])[0],
            "pageNo": params.get("pageNo", ["1"])[0],
            "numOfRows": params.get("numOfRows", ["100"])[0],
        }

        try:
            info_payload = self.fetch_json(LOCKER_INFO_API_URL, query)
            detail_payload = self.fetch_json(LOCKER_DETAIL_API_URL, query)
            try:
                realtime_payload = self.fetch_json(LOCKER_REALTIME_API_URL, query)
            except (HTTPError, URLError, json.JSONDecodeError):
                realtime_payload = {"body": {"item": []}}

            self.send_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "stdgCd": stdg_cd,
                    **normalize_lockers(info_payload, detail_payload, realtime_payload),
                },
            )
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            self.send_json(HTTPStatus.BAD_GATEWAY, {"error": "upstream_http_error", "status": exc.code, "detail": detail})
        except URLError as exc:
            self.send_json(HTTPStatus.BAD_GATEWAY, {"error": "upstream_connection_error", "detail": str(exc.reason)})
        except json.JSONDecodeError as exc:
            self.send_json(HTTPStatus.BAD_GATEWAY, {"error": "upstream_invalid_json", "detail": str(exc)})

    def handle_festivals(self) -> None:
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        event_start_date = params.get("eventStartDate", [""])[0]
        if not event_start_date:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "missing_eventStartDate"})
            return

        query = {
            "serviceKey": self.get_public_api_key(params),
            "numOfRows": params.get("numOfRows", ["200"])[0],
            "pageNo": params.get("pageNo", ["1"])[0],
            "MobileOS": params.get("MobileOS", ["ETC"])[0],
            "MobileApp": params.get("MobileApp", ["EcoTravel"])[0],
            "_type": params.get("_type", ["json"])[0],
            "arrange": params.get("arrange", ["A"])[0],
            "listYN": params.get("listYN", ["Y"])[0],
            "eventStartDate": event_start_date,
            "areaCode": params.get("areaCode", ["38"])[0],
        }

        sigungu_code = params.get("sigunguCode", [""])[0]
        if sigungu_code:
            query["sigunguCode"] = sigungu_code

        last_error: dict | None = None
        for upstream_url, source in (
            (FESTIVAL_SEARCH_API_URL, "searchFestival1"),
            (FESTIVAL_AREA_API_URL, "areaBasedList1"),
        ):
            fallback_query = dict(query)
            if upstream_url == FESTIVAL_AREA_API_URL:
                fallback_query.pop("eventStartDate", None)
                fallback_query["contentTypeId"] = "15"
            try:
                payload = self.fetch_json(upstream_url, fallback_query)
                self.send_json(HTTPStatus.OK, {"status": "ok", **normalize_festivals(payload, source)})
                return
            except HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                last_error = {"error": "upstream_http_error", "status": exc.code, "detail": detail, "source": source}
            except URLError as exc:
                last_error = {"error": "upstream_connection_error", "detail": str(exc.reason), "source": source}
            except json.JSONDecodeError as exc:
                last_error = {"error": "upstream_invalid_json", "detail": str(exc), "source": source}

        self.send_json(HTTPStatus.BAD_GATEWAY, last_error or {"error": "festival_upstream_failed"})


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
