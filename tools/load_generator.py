#!/usr/bin/env python3

from __future__ import annotations

import collections
import concurrent.futures
import json
import os
import random
import threading
import time
import urllib.error
import urllib.request


class Load:
    def __init__(self, urls: list[str], *, seed: int = 2026):
        if len(urls) < 2 or len(set(urls)) != len(urls):
            raise ValueError('Need at least two distinct app URLs')
        self.urls = [url.rstrip('/') for url in urls]
        self.lock = threading.Lock()
        self.ids = {url: collections.deque(maxlen=400) for url in self.urls}
        self.status_counts = collections.Counter()
        self.rng = random.Random(seed)

    @staticmethod
    def send(url: str, method: str, path: str, body: dict | None = None,
             *, synthetic_500: bool = False) -> tuple[int, dict | None]:
        headers = {'Accept': 'application/json'}
        data = None
        if body is not None:
            headers['Content-Type'] = 'application/json'
            data = json.dumps(body).encode('utf-8')
        if synthetic_500:
            headers['X-Demo-Error'] = '500'
        req = urllib.request.Request(url + path, method=method, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                code, raw = response.status, response.read()
        except urllib.error.HTTPError as error:
            code, raw = error.code, error.read()
        try:
            parsed = json.loads(raw) if raw else None
        except ValueError:
            parsed = None
        return code, parsed

    def seed_items(self):
        for url in self.urls:
            status, item = self.send(url, 'POST', '/items', {'name': 'initial-item'})
            if status != 201 or not isinstance(item, dict) or 'id' not in item:
                raise RuntimeError(f'Cannot initialize {url}: status={status} data={item}')
            self.ids[url].append(item['id'])
            print(f'Seed item in {url}: id={item["id"]}', flush=True)

    def choose_request(self, sequence: int) -> tuple[str, str, str, dict | None, bool]:
        """Return (URL, method, path, body, synthetic_500) without sending."""
        url = self.urls[sequence % len(self.urls)]
        phase = sequence % 100
        with self.lock:
            existing = self.rng.choice(list(self.ids[url])) if self.ids[url] else None
        if phase in (0, 75):
            return url, 'POST', '/items', {'name': 'synthetic-500'}, True
        if phase in (25, 50):
            return url, 'GET', '/items/987654321', None, False
        if sequence % 5 == 0 or existing is None:
            return url, 'POST', '/items', {'name': f'item-{sequence}'}, False
        if sequence % 5 in (1, 3):
            return url, 'GET', f'/items/{existing}', None, False
        return url, 'PUT', f'/items/{existing}', {'name': f'updated-{sequence}'}, False

    def send_one(self, sequence: int):
        url, method, path, body, synthetic = self.choose_request(sequence)
        try:
            code, response = self.send(url, method, path, body, synthetic_500=synthetic)
            with self.lock:
                self.status_counts[str(code)] += 1
                if method == 'POST' and code == 201 and isinstance(response, dict) and 'id' in response:
                    self.ids[url].append(response['id'])
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            with self.lock:
                self.status_counts['network-error'] += 1
            print(f'Warning: request failed: {type(error).__name__}: {error}', flush=True)


def target_rps(elapsed: float, start_rps: float, end_rps: float, ramp_seconds: float) -> float:
    if ramp_seconds <= 0:
        return end_rps
    return start_rps + (end_rps - start_rps) * min(max(elapsed / ramp_seconds, 0), 1)


def main():
    urls = [x.strip() for x in os.getenv('APP_URLS', '').split(',') if x.strip()]
    start = float(os.getenv('LOAD_START_RPS', '3'))
    target = float(os.getenv('LOAD_TARGET_RPS', '40'))
    ramp = float(os.getenv('LOAD_RAMP_SECONDS', '120'))
    if not (0 < start <= target <= 1000) or ramp < 0:
        raise ValueError('Invalid RPS/ramp: require 0 < start <= target <= 1000 and ramp >= 0')
    load = Load(urls)
    load.seed_items()
    started = time.monotonic()
    next_due = started
    reported = started
    sequence = 0
    pending: set[concurrent.futures.Future] = set()
    print(f'Load started: {start:g} -> {target:g} RPS total in {ramp:g} seconds '
          f'across {len(urls)} app replicas', flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as executor:
        try:
            while True:
                now = time.monotonic()
                current = target_rps(now - started, start, target, ramp)
                if now < next_due:
                    time.sleep(min(next_due - now, 0.1))
                    continue
                future = executor.submit(load.send_one, sequence)
                pending.add(future)
                future.add_done_callback(pending.discard)
                sequence += 1
                # Schedule one request at a time; catch up if only slightly late.
                next_due = max(next_due + 1.0 / current, now)
                if len(pending) >= 100:
                    concurrent.futures.wait(pending,
                                            return_when=concurrent.futures.FIRST_COMPLETED)
                if now - reported >= 10:
                    with load.lock:
                        totals = dict(load.status_counts)
                    print(json.dumps({
                        'elapsed_s': round(now - started),
                        'target_total_rps': round(current, 1),
                        'scheduled': sequence,
                        'responses': totals,
                        'in_flight': len(pending),
                    }), flush=True)
                    reported = now
        except KeyboardInterrupt:
            print('Load stopped', flush=True)


if __name__ == '__main__':
    main()
