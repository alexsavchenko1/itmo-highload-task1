#!/usr/bin/env python3
"""Проверки этапа 3 только средствами стандартной библиотеки Python 3.

Система проверяется по HTTP с хост-машины: Prometheus должен реально
собирать метрики с обоих контейнеров, а Grafana — иметь datasource.
"""
import base64
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PROM = 'http://127.0.0.1:9090'
GRAFANA = 'http://127.0.0.1:3000'
EXPECTED = {'app-1:8080': ('pod-1', 'dc-a'), 'app-2:8080': ('pod-2', 'dc-b')}
ROOT = Path(__file__).resolve().parents[1]

def fail(message):
    raise AssertionError(message)

def fetch_json(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.load(response)

def credentials():
    options = {}
    path = ROOT / '.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                options[key.strip()] = value.strip().strip('"').strip("'")
    import os
    return (
        os.getenv('GRAFANA_ADMIN_USER', options.get('GRAFANA_ADMIN_USER', 'admin')),
        os.getenv('GRAFANA_ADMIN_PASSWORD', options.get('GRAFANA_ADMIN_PASSWORD', 'change-me-local-only')),
    )

def check_prometheus():
    data = fetch_json(PROM + '/api/v1/targets?state=active')
    if data.get('status') != 'success':
        fail('Prometheus targets API did not succeed')
    targets = {}
    for item in data['data']['activeTargets']:
        if item.get('labels', {}).get('job') == 'items':
            targets[item['labels'].get('instance')] = item
    if set(targets) != set(EXPECTED):
        fail(f'Expected targets {sorted(EXPECTED)}, got {sorted(targets)}')
    for instance, target in targets.items():
        if target.get('health') != 'up':
            fail(f'{instance}: target is {target.get("health")}, error={target.get("lastError")}')
    print('OK: Prometheus collects both targets (UP)')

    # Запрос должен возвращать две отдельные временные серии с различными метками.
    query = urllib.parse.quote('app_http_requests_total{job="items",method="GET",route="/items/{id}",status="404"}')
    result = fetch_json(PROM + '/api/v1/query?query=' + query)
    if result.get('status') != 'success':
        fail('Prometheus instant query returned failure')
    series = {(entry['metric'].get('pod'), entry['metric'].get('dc'))
              for entry in result['data']['result']}
    expected_series = set(EXPECTED.values())
    if not expected_series.issubset(series):
        fail(f'Expected pod/dc labels {expected_series}, got {series}')
    print('OK: Prometheus contains separate request counters for both pod/dc labels')

def check_grafana():
    user, password = credentials()
    authorization = base64.b64encode(f'{user}:{password}'.encode()).decode()
    headers = {'Authorization': f'Basic {authorization}'}
    datasource = fetch_json(GRAFANA + '/api/datasources/uid/itmo-prometheus', headers)
    if datasource.get('uid') != 'itmo-prometheus':
        fail('Grafana datasource UID differs from itmo-prometheus')
    if datasource.get('url') != 'http://prometheus:9090':
        fail(f'Grafana datasource has wrong URL: {datasource.get("url")}')
    if datasource.get('type') != 'prometheus':
        fail('Grafana datasource type is not prometheus')
    print('OK: Grafana has provisioned Prometheus datasource with fixed UID')

def run():
    # После запуска Docker контейнер может пройти healthcheck раньше,
    # чем Prometheus выполнит первый scrape, поэтому ждём до 90 сек.
    deadline = time.monotonic() + 90
    last_error = None
    while time.monotonic() < deadline:
        try:
            check_prometheus()
            check_grafana()
            print('SUCCESS: TASK1 stages 1–3 are operational')
            return
        except (AssertionError, urllib.error.URLError, TimeoutError, KeyError, ValueError) as error:
            last_error = error
            time.sleep(3)
    fail(f'Infrastructure is not ready after checks: {last_error}')

if __name__ == '__main__':
    try:
        run()
    except Exception as error:
        print(f'FAIL: {error}', file=sys.stderr)
        sys.exit(1)
