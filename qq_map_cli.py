#!/usr/bin/env python3
"""
Tencent Location Service CLI tool.

Examples:
  Create a config file in the current directory:
  python3 qq_map_cli.py setup --key "your-key"

  Then run:
  python3 qq_map_cli.py distance-matrix \
    --mode driving \
    --origin 39.984154,116.307490 \
    --destination 39.908692,116.397477

  python3 qq_map_cli.py geocoder \
    --address "北京市海淀区彩和坊路海淀西大街74号"

  python3 qq_map_cli.py address-distance \
    --from-address "北京市海淀区中关村大街27号" \
    --to-address "北京市朝阳区望京街10号"
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import certifi


DISTANCE_MATRIX_API_URL = "https://apis.map.qq.com/ws/distance/v1/matrix"
GEOCODER_API_URL = "https://apis.map.qq.com/ws/geocoder/v1/"
DISTANCE_MATRIX_MODES = ("driving", "walking", "bicycling", "straight")
HTTP_METHODS = ("auto", "get", "post")
GEOCODER_POLICIES = (0, 1)
DEFAULT_CONFIG_PATH = Path.cwd() / "qq_map_cli_config.json"
LEGACY_CONFIG_PATH = Path.cwd() / "qq_distance_matrix_config.json"


class ApiError(Exception):
    """Raised when the Tencent API returns an error."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qq_map_cli.py",
        description="Tencent Location Service command line tool.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup_parser = subparsers.add_parser(
        "setup",
        help="Create or update a local config file for the CLI.",
        description="Create or update qq_map_cli_config.json in the current workspace.",
    )
    setup_parser.add_argument(
        "--config",
        help="Config file path. Default: ./qq_map_cli_config.json",
    )
    setup_parser.add_argument(
        "--key",
        help="Tencent Map key to write into the config file.",
    )
    setup_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the config file if it already exists.",
    )
    setup_parser.set_defaults(handler=run_setup)

    distance_parser = subparsers.add_parser(
        "distance-matrix",
        help="Calculate distances with the distance matrix API.",
        description="Calculate distances with Tencent Map distance matrix API.",
    )
    add_common_args(distance_parser)
    distance_parser.add_argument(
        "--mode",
        choices=DISTANCE_MATRIX_MODES,
        default="driving",
        help="Routing mode. Default: driving.",
    )
    distance_parser.add_argument(
        "--origin",
        action="append",
        default=[],
        help="Origin point in simple format: lat,lng . Repeat for multiple origins.",
    )
    distance_parser.add_argument(
        "--destination",
        action="append",
        default=[],
        help="Destination point in simple format: lat,lng . Repeat for multiple destinations.",
    )
    distance_parser.add_argument(
        "--http-method",
        choices=HTTP_METHODS,
        default="auto",
        help="HTTP method selection. Default: auto (GET for straight, POST otherwise).",
    )
    distance_parser.add_argument(
        "--from-raw",
        dest="from_raw",
        help="Raw 'from' string in official API format. Overrides --origin.",
    )
    distance_parser.add_argument(
        "--to-raw",
        dest="to_raw",
        help="Raw 'to' string in official API format. Overrides --destination.",
    )
    distance_parser.set_defaults(handler=run_distance_matrix)

    geocoder_parser = subparsers.add_parser(
        "geocoder",
        help="Convert address text to coordinates.",
        description="Convert a text address to coordinates with Tencent Map geocoder API.",
    )
    add_common_args(geocoder_parser)
    geocoder_parser.add_argument(
        "--address",
        required=True,
        help="Address to geocode. Include city name for better accuracy.",
    )
    geocoder_parser.add_argument(
        "--policy",
        type=int,
        choices=GEOCODER_POLICIES,
        default=0,
        help="Parsing policy: 0=strict, 1=relaxed. Default: 0.",
    )
    geocoder_parser.set_defaults(handler=run_geocoder)

    address_distance_parser = subparsers.add_parser(
        "address-distance",
        help="Resolve two addresses and calculate the distance between them.",
        description=(
            "Resolve two text addresses with the geocoder API and then calculate "
            "the distance between them with the distance matrix API."
        ),
    )
    add_common_args(address_distance_parser)
    address_distance_parser.add_argument(
        "--from-address",
        required=True,
        help="Start address. Include city name for better accuracy.",
    )
    address_distance_parser.add_argument(
        "--to-address",
        required=True,
        help="Destination address. Include city name for better accuracy.",
    )
    address_distance_parser.add_argument(
        "--mode",
        choices=DISTANCE_MATRIX_MODES,
        default="driving",
        help="Routing mode for distance calculation. Default: driving.",
    )
    address_distance_parser.add_argument(
        "--policy",
        type=int,
        choices=GEOCODER_POLICIES,
        default=0,
        help="Geocoder parsing policy: 0=strict, 1=relaxed. Default: 0.",
    )
    address_distance_parser.add_argument(
        "--http-method",
        choices=HTTP_METHODS,
        default="auto",
        help="Distance matrix HTTP method selection. Default: auto.",
    )
    address_distance_parser.set_defaults(handler=run_address_distance)

    return parser


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--key",
        help="Tencent Map key. Overrides config file and QQ_MAP_KEY environment variable.",
    )
    parser.add_argument(
        "--config",
        help="Config file path. Default: ./qq_map_cli_config.json",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP timeout in seconds. Default: 10.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw JSON response instead of formatted output.",
    )


def select_config_path(config_path: str | None) -> Path:
    if config_path:
        return Path(config_path)
    if DEFAULT_CONFIG_PATH.exists():
        return DEFAULT_CONFIG_PATH
    if LEGACY_CONFIG_PATH.exists():
        return LEGACY_CONFIG_PATH
    return DEFAULT_CONFIG_PATH


def load_config(config_path: str | None) -> dict[str, Any]:
    path = select_config_path(config_path)
    if not path.exists():
        return {}

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid config JSON in {path}: {exc}") from exc


def resolve_key(args: argparse.Namespace) -> str | None:
    config = load_config(args.config)
    cli_key = args.key.strip() if isinstance(args.key, str) else args.key
    config_key = config.get("key")
    if isinstance(config_key, str):
        config_key = config_key.strip()
    env_key = os.environ.get("QQ_MAP_KEY")
    if isinstance(env_key, str):
        env_key = env_key.strip()
    return cli_key or config_key or env_key


def ensure_key(args: argparse.Namespace) -> str:
    key = resolve_key(args)
    if not key:
        raise ValueError(
            "Missing key. Use --key, set qq_map_cli_config.json, or set QQ_MAP_KEY."
        )
    return key


def create_config_file(*, config_path: str | None, key: str | None, force: bool) -> Path:
    path = select_config_path(config_path)
    if path.exists() and not force:
        raise ValueError(
            f"Config file already exists: {path}. Use --force to overwrite it."
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    content = {"key": key.strip() if isinstance(key, str) else ""}
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def run_setup(args: argparse.Namespace) -> int:
    path = create_config_file(config_path=args.config, key=args.key, force=args.force)
    print(f"config_path: {path}")
    if args.key and args.key.strip():
        print("key_status: written")
    else:
        print("key_status: empty")
        print("next_step: edit the config file and fill in the Tencent Map key, or rerun setup with --key.")
    return 0


def request_json(
    *,
    url: str,
    method: str,
    timeout: float,
    query_params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    query_string = urllib.parse.urlencode(query_params or {})
    full_url = f"{url}?{query_string}" if query_string else url
    data = None
    headers: dict[str, str] = {}

    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        url=full_url,
        data=data,
        headers=headers,
        method=method,
    )
    ssl_context = ssl.create_default_context(cafile=certifi.where())

    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ssl_context) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise ApiError(f"HTTP {exc.code}: {error_body}") from exc
    except ssl.SSLCertVerificationError as exc:
        raise ApiError(
            "TLS certificate verification failed. "
            "Please install dependencies from requirements.txt, or use the packaged binary "
            "which bundles CA certificates. "
            f"Details: {exc}"
        ) from exc
    except urllib.error.URLError as exc:
        raise ApiError(f"Request failed: {exc.reason}") from exc

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ApiError(f"Invalid JSON response: {body}") from exc

    if data.get("status") != 0:
        raise ApiError(
            f"API error {data.get('status')}: {data.get('message', 'Unknown error')}"
        )

    return data


def join_points(raw_value: str | None, simple_values: list[str], label: str) -> str:
    if raw_value:
        return raw_value.strip()
    if not simple_values:
        raise ValueError(f"Please provide {label}.")
    return ";".join(item.strip() for item in simple_values if item.strip())


def estimate_count(value: str, separator: str = ";") -> int:
    return len([part for part in value.split(separator) if part.strip()])


def validate_distance_matrix_args(args: argparse.Namespace) -> tuple[str, str]:
    from_value = join_points(args.from_raw, args.origin, "origins")
    to_value = join_points(args.to_raw, args.destination, "destinations")

    origin_count = estimate_count(from_value)
    destination_count = estimate_count(to_value)

    if destination_count == 1:
        if origin_count > 200:
            raise ValueError(
                "Too many origins. For many-to-one requests, the limit is 200."
            )
    elif origin_count == 1:
        if destination_count > 200:
            raise ValueError(
                "Too many destinations. For one-to-many requests, the limit is 200."
            )
    elif (
        origin_count > 50
        or destination_count > 50
        or origin_count * destination_count > 625
    ):
        raise ValueError(
            "For many-to-many requests, each side must be <= 50 and "
            "origin_count * destination_count must be <= 625."
        )

    return from_value, to_value


def call_distance_matrix(
    *,
    key: str,
    mode: str,
    from_value: str,
    to_value: str,
    timeout: float,
    http_method: str,
) -> dict[str, Any]:
    method = http_method
    if method == "auto":
        method = "get" if mode == "straight" else "post"

    if method == "post" and mode == "straight":
        raise ApiError("POST does not support straight mode according to the official docs.")

    if method == "get":
        return request_json(
            url=DISTANCE_MATRIX_API_URL,
            method="GET",
            timeout=timeout,
            query_params={"key": key, "mode": mode, "from": from_value, "to": to_value},
        )

    return request_json(
        url=DISTANCE_MATRIX_API_URL,
        method="POST",
        timeout=timeout,
        query_params={"mode": mode},
        json_body={"key": key, "from": from_value, "to": to_value},
    )


def format_duration(seconds: Any) -> str:
    if seconds is None:
        return "-"
    try:
        total_seconds = int(seconds)
    except (TypeError, ValueError):
        return str(seconds)

    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h{minutes}m{secs}s"
    if minutes:
        return f"{minutes}m{secs}s"
    return f"{secs}s"


def print_distance_matrix(data: dict[str, Any], origins: list[str], destinations: list[str]) -> None:
    rows = data.get("result", {}).get("rows", [])
    if not rows:
        print("No result rows returned.")
        return

    for row_index, row in enumerate(rows):
        origin_label = origins[row_index] if row_index < len(origins) else f"origin_{row_index + 1}"
        print(f"[{origin_label}]")
        elements = row.get("elements", [])
        for col_index, element in enumerate(elements):
            destination_label = (
                destinations[col_index]
                if col_index < len(destinations)
                else f"destination_{col_index + 1}"
            )
            distance = element.get("distance", "-")
            duration = format_duration(element.get("duration"))
            element_status = element.get("status")

            if element_status is None:
                print(f"  -> {destination_label}: distance={distance}m, duration={duration}")
            else:
                print(
                    f"  -> {destination_label}: distance={distance}m, "
                    f"duration={duration}, status={element_status}"
                )
        print()


def run_distance_matrix(args: argparse.Namespace) -> int:
    key = ensure_key(args)
    from_value, to_value = validate_distance_matrix_args(args)
    data = call_distance_matrix(
        key=key,
        mode=args.mode,
        from_value=from_value,
        to_value=to_value,
        timeout=args.timeout,
        http_method=args.http_method,
    )

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    origins = [item for item in from_value.split(";") if item.strip()]
    destinations = [item for item in to_value.split(";") if item.strip()]
    print_distance_matrix(data, origins, destinations)
    return 0


def validate_geocoder_args(args: argparse.Namespace) -> str:
    address = args.address.strip()
    if not address:
        raise ValueError("Address cannot be empty.")
    return address


def call_geocoder(*, key: str, address: str, policy: int, timeout: float) -> dict[str, Any]:
    return request_json(
        url=GEOCODER_API_URL,
        method="GET",
        timeout=timeout,
        query_params={
            "key": key,
            "address": address,
            "policy": policy,
            "output": "json",
        },
    )


def geocode_address(*, key: str, address: str, policy: int, timeout: float) -> tuple[str, dict[str, Any]]:
    data = call_geocoder(key=key, address=address, policy=policy, timeout=timeout)
    result = data.get("result", {})
    location = result.get("location", {})
    lat = location.get("lat")
    lng = location.get("lng")

    if lat is None or lng is None:
        raise ApiError(f"Geocoder returned no location for address: {address}")

    return f"{lat},{lng}", data


def print_geocoder_result(data: dict[str, Any]) -> None:
    result = data.get("result", {})
    location = result.get("location", {})
    components = result.get("address_components", {})
    ad_info = result.get("ad_info", {})

    print(f"lat: {location.get('lat', '')}")
    print(f"lng: {location.get('lng', '')}")
    print(
        "province/city/district: "
        f"{components.get('province', '')} / "
        f"{components.get('city', '')} / "
        f"{components.get('district', '')}"
    )
    print(
        "street/street_number: "
        f"{components.get('street', '')} / "
        f"{components.get('street_number', '')}"
    )
    print(f"adcode: {ad_info.get('adcode', '')}")
    print(f"reliability: {result.get('reliability', '')}")
    print(f"level: {result.get('level', '')}")
    if result.get("title"):
        print(f"title_deprecated: {result.get('title', '')}")
    print(f"request_id: {data.get('request_id', '')}")


def run_geocoder(args: argparse.Namespace) -> int:
    key = ensure_key(args)
    address = validate_geocoder_args(args)
    data = call_geocoder(
        key=key,
        address=address,
        policy=args.policy,
        timeout=args.timeout,
    )

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    print_geocoder_result(data)
    return 0


def print_address_distance_result(
    *,
    from_address: str,
    to_address: str,
    from_coord: str,
    to_coord: str,
    distance_matrix_data: dict[str, Any],
) -> None:
    rows = distance_matrix_data.get("result", {}).get("rows", [])
    element = {}
    if rows and rows[0].get("elements"):
        element = rows[0]["elements"][0]

    distance = element.get("distance", "-")
    duration = format_duration(element.get("duration"))
    element_status = element.get("status")

    print(f"from_address: {from_address}")
    print(f"from_coord: {from_coord}")
    print(f"to_address: {to_address}")
    print(f"to_coord: {to_coord}")
    print(f"distance_meters: {distance}")
    print(f"duration: {duration}")
    if element_status is not None:
        print(f"matrix_status: {element_status}")


def run_address_distance(args: argparse.Namespace) -> int:
    key = ensure_key(args)
    from_address = args.from_address.strip()
    to_address = args.to_address.strip()

    if not from_address:
        raise ValueError("Start address cannot be empty.")
    if not to_address:
        raise ValueError("Destination address cannot be empty.")

    from_coord, from_geocoder_data = geocode_address(
        key=key,
        address=from_address,
        policy=args.policy,
        timeout=args.timeout,
    )
    to_coord, to_geocoder_data = geocode_address(
        key=key,
        address=to_address,
        policy=args.policy,
        timeout=args.timeout,
    )
    distance_matrix_data = call_distance_matrix(
        key=key,
        mode=args.mode,
        from_value=from_coord,
        to_value=to_coord,
        timeout=args.timeout,
        http_method=args.http_method,
    )

    if args.json:
        print(
            json.dumps(
                {
                    "from_address": from_address,
                    "to_address": to_address,
                    "from_coord": from_coord,
                    "to_coord": to_coord,
                    "from_geocoder": from_geocoder_data,
                    "to_geocoder": to_geocoder_data,
                    "distance_matrix": distance_matrix_data,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print_address_distance_result(
        from_address=from_address,
        to_address=to_address,
        from_coord=from_coord,
        to_coord=to_coord,
        distance_matrix_data=distance_matrix_data,
    )
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        return args.handler(args)
    except (ValueError, ApiError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
