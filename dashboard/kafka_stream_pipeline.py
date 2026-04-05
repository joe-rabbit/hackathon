#!/usr/bin/env python3
"""Async Kafka pipeline for Mochi analytics.

Producers tail local JSONL files and publish records to Kafka topics.
Consumer reads topics, transforms to Influx line protocol, writes in batches,
and updates ingest heartbeat for the Tamagochi /health command.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from push_usage_to_influx import (
    DEFAULT_INGEST_HEARTBEAT_PATH,
    DEFAULT_LOG_PATH,
    DEFAULT_PROMPT_EFFICIENCY_LOG_PATH,
    build_lines,
    build_prompt_efficiency_lines,
    validate_measurements,
    write_heartbeat,
    write_to_influx,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run async Kafka stream pipeline for Influx ingestion.")
    p.add_argument("--bootstrap-servers", default="localhost:9092")
    p.add_argument("--usage-topic", default="mochi.usage.snapshots")
    p.add_argument("--prompt-topic", default="mochi.prompt.efficiency")
    p.add_argument("--group-id", default="mochi-influx-writer")
    p.add_argument("--mode", choices=["all", "producer", "consumer"], default="all")
    p.add_argument("--from-start", action="store_true", help="Publish existing file contents before tailing.")
    p.add_argument("--poll-interval", type=float, default=1.0)
    p.add_argument("--flush-interval", type=float, default=2.0)
    p.add_argument("--batch-size", type=int, default=100)
    p.add_argument("--duration-s", type=float, default=0.0, help="Auto-stop after N seconds (0 = run forever).")

    p.add_argument("--log-file", type=Path, default=DEFAULT_LOG_PATH)
    p.add_argument("--prompt-efficiency-log-file", type=Path, default=DEFAULT_PROMPT_EFFICIENCY_LOG_PATH)
    p.add_argument("--heartbeat-file", type=Path, default=DEFAULT_INGEST_HEARTBEAT_PATH)
    p.add_argument("--validate-measurements", action="store_true")

    p.add_argument("--influx-url", default="http://localhost:8086")
    p.add_argument("--org", default="hackathon")
    p.add_argument("--bucket", default="metrics")
    p.add_argument("--token", required=True)
    p.add_argument("--grid-kg-co2e-per-kwh", type=float, default=0.4)
    return p.parse_args()


def parse_json_line(raw: str) -> dict[str, Any] | None:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(value, dict):
        return value
    return None


def read_initial_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            obj = parse_json_line(line)
            if obj is not None:
                out.append(obj)
    return out


def read_new_records(path: Path, offset: int) -> tuple[list[dict[str, Any]], int]:
    if not path.exists():
        return [], offset

    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        f.seek(0, 2)
        end = f.tell()
        if offset > end:
            offset = 0
        f.seek(offset)
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            obj = parse_json_line(line)
            if obj is not None:
                out.append(obj)
        return out, f.tell()


async def producer_loop(
    producer: AIOKafkaProducer,
    path: Path,
    topic: str,
    poll_interval: float,
    from_start: bool,
    stop_event: asyncio.Event,
) -> None:
    offset = 0
    if from_start:
        for record in read_initial_records(path):
            await producer.send_and_wait(topic, json.dumps(record, ensure_ascii=True).encode("utf-8"))
    elif path.exists():
        with path.open("r", encoding="utf-8", errors="replace") as f:
            f.seek(0, 2)
            offset = f.tell()

    while not stop_event.is_set():
        records, offset = read_new_records(path, offset)
        for record in records:
            await producer.send_and_wait(topic, json.dumps(record, ensure_ascii=True).encode("utf-8"))
        await asyncio.sleep(max(0.1, poll_interval))


async def consumer_loop(args: argparse.Namespace, stop_event: asyncio.Event) -> None:
    consumer = AIOKafkaConsumer(
        args.usage_topic,
        args.prompt_topic,
        bootstrap_servers=args.bootstrap_servers,
        group_id=args.group_id,
        enable_auto_commit=True,
        auto_offset_reset="earliest",
    )
    await consumer.start()

    usage_buffer: list[str] = []
    prompt_buffer: list[str] = []
    last_flush = time.time()
    points_written = 0
    snapshots_ingested = 0
    prompt_ingested = 0

    try:
        while not stop_event.is_set():
            batch = await consumer.getmany(timeout_ms=500, max_records=max(1, args.batch_size))
            for tp, messages in batch.items():
                for msg in messages:
                    try:
                        payload = json.loads(msg.value.decode("utf-8", errors="replace"))
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(payload, dict):
                        continue

                    if tp.topic == args.usage_topic:
                        usage_buffer.extend(build_lines(payload, args.grid_kg_co2e_per_kwh))
                        snapshots_ingested += 1
                    elif tp.topic == args.prompt_topic:
                        prompt_buffer.extend(build_prompt_efficiency_lines(payload))
                        prompt_ingested += 1

            should_flush = (
                len(usage_buffer) + len(prompt_buffer) >= max(1, args.batch_size)
                or (time.time() - last_flush) >= max(0.2, args.flush_interval)
            )
            if should_flush and (usage_buffer or prompt_buffer):
                if usage_buffer:
                    write_to_influx(
                        args.influx_url,
                        args.org,
                        args.bucket,
                        args.token,
                        "\n".join(usage_buffer),
                    )
                if prompt_buffer:
                    write_to_influx(
                        args.influx_url,
                        args.org,
                        args.bucket,
                        args.token,
                        "\n".join(prompt_buffer),
                    )
                points_written += len(usage_buffer) + len(prompt_buffer)
                usage_buffer.clear()
                prompt_buffer.clear()
                last_flush = time.time()

                validation: dict[str, bool] | None = None
                if args.validate_measurements:
                    validation = validate_measurements(
                        url=args.influx_url,
                        org=args.org,
                        bucket=args.bucket,
                        token=args.token,
                    )

                heartbeat: dict[str, Any] = {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "status": "ok",
                    "mode": "kafka-stream",
                    "snapshots_ingested": snapshots_ingested,
                    "prompt_efficiency_records_ingested": prompt_ingested,
                    "points_written": points_written,
                    "influx_url": args.influx_url,
                    "org": args.org,
                    "bucket": args.bucket,
                    "kafka_bootstrap_servers": args.bootstrap_servers,
                    "kafka_topics": {
                        "usage": args.usage_topic,
                        "prompt_efficiency": args.prompt_topic,
                    },
                }
                if validation is not None:
                    heartbeat["validation"] = validation
                write_heartbeat(args.heartbeat_file, heartbeat)
    finally:
        await consumer.stop()


async def run(args: argparse.Namespace) -> int:
    stop_event = asyncio.Event()
    tasks: list[asyncio.Task] = []
    producer: AIOKafkaProducer | None = None

    try:
        if args.mode in {"all", "producer"}:
            producer = AIOKafkaProducer(bootstrap_servers=args.bootstrap_servers)
            await producer.start()
            tasks.append(
                asyncio.create_task(
                    producer_loop(
                        producer,
                        args.log_file,
                        args.usage_topic,
                        args.poll_interval,
                        args.from_start,
                        stop_event,
                    )
                )
            )
            tasks.append(
                asyncio.create_task(
                    producer_loop(
                        producer,
                        args.prompt_efficiency_log_file,
                        args.prompt_topic,
                        args.poll_interval,
                        args.from_start,
                        stop_event,
                    )
                )
            )

        if args.mode in {"all", "consumer"}:
            tasks.append(asyncio.create_task(consumer_loop(args, stop_event)))

        if args.duration_s > 0:
            await asyncio.sleep(args.duration_s)
            stop_event.set()
        else:
            await asyncio.gather(*tasks)

        if stop_event.is_set() and tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        return 0
    finally:
        stop_event.set()
        if producer is not None:
            await producer.stop()


def main() -> int:
    args = parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
