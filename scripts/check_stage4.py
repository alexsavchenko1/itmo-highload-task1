#!/usr/bin/env python3
"""Check dashboard generation, technical-route exclusion and active load."""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

GRAFANA = 'http://127.0.0.1:3000'
PROMETHEUS = 'http://127.0.0.1:9090'
ROOT = Path(__file__).resolve().parents[1]
UID = 'itmo-items-golden-signals'


def credentials():
    env = {}
    path = ROOT / '.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return (os.getenv('GRAFANA_ADMIN_USER', env.get('GRAFANA_ADMIN_USER', 'admin')),
            os.getenv('GRAFANA_ADMIN_PASSWORD', env.get('GRAFANA_ADMIN_PASSWORD', '')))


def fetch_json(url, *, basic_auth=None):
    headers = {}
    if basic_auth:
        token = base64.b64encode(':'.join(basic_auth).encode()).decode()
        headers['Authorization'] = 'Basic ' + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=6) as response:
        return json.load(response)


def query(expr):
    payload = fetch_json(PROMETHEUS + '/api/v1/query?query=' + urllib.parse.quote(expr))
    assert payload['status'] == 'success', f'Prometheus query failed: {payload}'
    return payload['data']['result']


def check_dashboard():
    entry = fetch_json(GRAFANA + '/api/dashboards/uid/' + UID, basic_auth=credentials())
    db = entry['dashboard']
    assert db['editable'] is False, 'Dashboard must be non-editable'
    found_vars = {v['name']: v for v in db['templating']['list']}
    assert {'dc', 'pod'} == set(found_vars), found_vars
    for name in ('dc', 'pod'):
        assert found_vars[name]['multi'] is True and found_vars[name]['includeAll'] is True
    assert len(db['panels']) == 9, f'Expected 9 panels (3 handlers x 3), got {len(db["panels"])}'
    for panel in db['panels']:
        exprs = [t['expr'] for t in panel['targets']]
        for expr in exprs:
            assert 'method=' in expr and 'route=' in expr, expr
            assert 'dc=~"${dc:regex}"' in expr, expr
            assert 'pod=~"${pod:regex}"' in expr, expr
            if 'histogram_quantile' in expr:
                assert 'sum by (le) (rate(' in expr, expr
            if 'errors' in panel['title']:
                assert 'status=~"4..|5.."' in expr and 'sum by (status)' in expr, expr
    names = {p['title'].split(' | ')[0] for p in db['panels']}
    assert names == {'POST /items', 'GET /items/{id}', 'PUT /items/{id}'}, names
    print('OK: dashboard is generated from 3 handlers (9 panels), non-editable, with dc/pod multi-select')
    print('OK: rate(), histogram_quantile() and HTTP error queries are correctly constructed')


def check_technical_exclusion():
    result = query('app_http_requests_total{job="items",route=~"/health|/metrics|/handlers|/error"}')
    assert not result, f'Service routes are counted as business traffic: {result}'
    print('OK: /health, /metrics, /handlers, /error excluded from business HTTP metrics')


def traffic_by_pod():
    result = query('sum by (pod) (app_http_requests_total{job="items"})')
    return {r['metric']['pod']: float(r['value'][1]) for r in result}


def check_load_in_progress():
    deadline = time.monotonic() + 70
    baseline = traffic_by_pod()
    while time.monotonic() < deadline:
        time.sleep(10)
        now = traffic_by_pod()
        if all(now.get(p, 0) >= baseline.get(p, 0) + 4 for p in ('pod-1', 'pod-2')):
            print('OK: both pods receive new business requests from background load generator')
            return
    raise AssertionError(f'No sustained traffic increase on both pods: before={baseline}, after={now}')


def run():
    deadline = time.monotonic() + 90
    last_error = None
    while time.monotonic() < deadline:
        try:
            check_dashboard()
            check_technical_exclusion()
            check_load_in_progress()
            print('SUCCESS: TASK1 all stages operational, dashboard and load are working')
            return
        except (AssertionError, KeyError, OSError, ValueError, TimeoutError) as error:
            last_error = error
            print(f'Waiting for stage 4: {error}', flush=True)
            time.sleep(3)
    raise AssertionError(f'Stage 4 not ready: {last_error}')


if __name__ == '__main__':
    try:
        run()
    except Exception as error:
        print(f'FAIL: {error}', file=sys.stderr)
        sys.exit(1)
