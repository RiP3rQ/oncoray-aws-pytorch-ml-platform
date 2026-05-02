from __future__ import annotations

import argparse
import asyncio
import base64
import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx

DEFAULT_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGMwMDAAAAIhAIFbR60ZAAAAAElFTkSuQmCC"
)


@dataclass(frozen=True)
class RequestResult:
    status_code: int | None
    latency_ms: float
    error: str | None = None


async def run_benchmark(
    *,
    url: str,
    image_data: bytes,
    filename: str,
    request_count: int,
    concurrency: int,
    timeout_seconds: float,
) -> dict[str, Any]:
    semaphore = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        tasks = [
            asyncio.create_task(run_one_request(client, semaphore, url, image_data, filename))
            for _ in range(request_count)
        ]
        started_at = perf_counter()
        results = await asyncio.gather(*tasks)
        total_seconds = perf_counter() - started_at

    latencies = sorted(result.latency_ms for result in results)
    failures = [result for result in results if result.error is not None or result.status_code != 200]
    return {
        "url": url,
        "requests": request_count,
        "concurrency": concurrency,
        "total_seconds": round(total_seconds, 4),
        "requests_per_second": round(request_count / total_seconds, 4) if total_seconds > 0 else None,
        "latency_ms": {
            "min": round(latencies[0], 4),
            "p50": round(percentile(latencies, 50), 4),
            "p95": round(percentile(latencies, 95), 4),
            "max": round(latencies[-1], 4),
        },
        "failures": len(failures),
        "failure_examples": [
            {
                "status_code": result.status_code,
                "error": result.error,
                "latency_ms": round(result.latency_ms, 4),
            }
            for result in failures[:5]
        ],
    }


async def run_one_request(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    url: str,
    image_data: bytes,
    filename: str,
) -> RequestResult:
    async with semaphore:
        started_at = perf_counter()
        try:
            response = await client.post(
                f"{url.rstrip('/')}/predict",
                files={"image": (filename, image_data, "application/octet-stream")},
            )
        except httpx.HTTPError as exc:
            return RequestResult(
                status_code=None,
                latency_ms=elapsed_ms(started_at),
                error=str(exc),
            )
        return RequestResult(status_code=response.status_code, latency_ms=elapsed_ms(started_at))


def percentile(sorted_values: list[float], percentile_value: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (len(sorted_values) - 1) * (percentile_value / 100)
    lower = int(rank)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = rank - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def elapsed_ms(started_at: float) -> float:
    return (perf_counter() - started_at) * 1000


def load_image(path: Path | None) -> tuple[bytes, str]:
    if path is None:
        return DEFAULT_PNG, "benchmark.png"
    return path.read_bytes(), path.name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark model-service /predict latency and throughput.")
    parser.add_argument("--url", default="http://127.0.0.1:8001", help="Base URL for model-service.")
    parser.add_argument("--image", type=Path, default=None, help="Optional image file. Uses tiny PNG when omitted.")
    parser.add_argument("--requests", type=int, default=20, help="Total requests to send.")
    parser.add_argument("--concurrency", type=int, default=4, help="Concurrent in-flight requests.")
    parser.add_argument("--timeout-seconds", type=float, default=30.0, help="Per-request timeout.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.requests < 1:
        raise ValueError("--requests must be at least 1.")
    if args.concurrency < 1:
        raise ValueError("--concurrency must be at least 1.")

    image_data, filename = load_image(args.image)
    result = asyncio.run(
        run_benchmark(
            url=args.url,
            image_data=image_data,
            filename=filename,
            request_count=args.requests,
            concurrency=args.concurrency,
            timeout_seconds=args.timeout_seconds,
        )
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
