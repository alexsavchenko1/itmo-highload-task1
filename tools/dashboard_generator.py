#!/usr/bin/env python3
"""Generate a non-editable Grafana dashboard from live Spring MVC /handlers.

No business HTTP routes are hardcoded in this program. Only the common
observability contract (metric names and labels) is used to construct PromQL.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

GRAFANA_DATASOURCE_UID = 'itmo-prometheus'
DASHBOARD_UID = 'itmo-items-golden-signals'
TECHNICAL_ROUTES = frozenset({'/metrics', '/health', '/handlers', '/error'})
COUNTER = 'app_http_requests_total'
BUCKETS = 'app_http_request_duration_seconds_bucket'


def request_json(url: str, *, method: str = 'GET', payload: dict | None = None,
                 username: str | None = None, password: str | None = None) -> Any:
    headers = {'Accept': 'application/json'}
    if username is not None and password is not None:
        token = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('ascii')
        headers['Authorization'] = 'Basic ' + token
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    request = urllib.request.Request(url, headers=headers, data=data, method=method)
    with urllib.request.urlopen(request, timeout=8) as response:
        return json.load(response)


def discover_handlers(app_urls: list[str]) -> list[tuple[str, str]]:
    if not app_urls:
        raise ValueError('At least one app URL is required')
    result = set()
    for app_url in app_urls:
        payload = request_json(app_url.rstrip('/') + '/handlers')
        if not isinstance(payload, list):
            raise ValueError(f'{app_url}/handlers must return a JSON array')
        for item in payload:
            if not isinstance(item, dict):
                raise ValueError('Invalid handler descriptor')
            method, route = item.get('method'), item.get('route')
            if not isinstance(method, str) or not method.isalpha():
                raise ValueError(f'Invalid HTTP method: {method!r}')
            if not isinstance(route, str) or not route.startswith('/'):
                raise ValueError(f'Invalid route: {route!r}')
            if route not in TECHNICAL_ROUTES:
                result.add((method.upper(), route))
    if not result:
        raise ValueError('No business handlers found in /handlers')
    return sorted(result, key=lambda item: (item[1], item[0]))


def promql_quoted(value: str) -> str:
    """Escape PromQL string literal and Grafana variable syntax in route names."""
    # JSON strings are valid PromQL double-quoted string literals for route names.
    # Escape '$' and '[' via unicode escapes to avoid Grafana template expansion.
    return json.dumps(value, ensure_ascii=False).replace('$', r'\u0024').replace('[', r'\u005b')


def selector(method: str, route: str, *, errors_only: bool = False) -> str:
    result = (
        f'method={promql_quoted(method)},route={promql_quoted(route)},'
        'dc=~"${dc:regex}",pod=~"${pod:regex}"'
    )
    if errors_only:
        result += ',status=~"4..|5.."'
    return '{' + result + '}'


def datasource() -> dict[str, str]:
    return {'type': 'prometheus', 'uid': GRAFANA_DATASOURCE_UID}


def target(expression: str, legend: str, ref_id: str) -> dict:
    return {
        'refId': ref_id, 'expr': expression, 'legendFormat': legend,
        'datasource': datasource(), 'format': 'time_series',
        'editorMode': 'code', 'range': True,
    }


def panel(panel_id: int, title: str, x: int, y: int, unit: str, targets: list[dict]) -> dict:
    return {
        'id': panel_id, 'type': 'timeseries', 'title': title,
        'datasource': datasource(),
        'gridPos': {'h': 9, 'w': 8, 'x': x, 'y': y},
        'fieldConfig': {'defaults': {'unit': unit, 'min': 0}, 'overrides': []},
        'options': {
            'legend': {'showLegend': True, 'displayMode': 'list', 'placement': 'bottom'},
            'tooltip': {'mode': 'multi', 'sort': 'desc'},
        },
        'targets': targets,
    }


def variable(name: str, query: str) -> dict:
    return {
        'name': name, 'label': name.upper(), 'type': 'query',
        'datasource': datasource(), 'query': query, 'definition': query,
        'refresh': 2, 'multi': True, 'includeAll': True, 'allValue': '.*',
        'sort': 1, 'regex': '', 'hide': 0,
        'current': {'selected': True, 'text': ['All'], 'value': ['$__all']},
        'options': [],
    }


def build_dashboard(handlers: list[tuple[str, str]]) -> dict:
    if not handlers:
        raise ValueError('Dashboard requires at least one business handler')
    panels = []
    for index, (method, route) in enumerate(handlers):
        label = f'{method} {route}'
        labels = selector(method, route)
        bucket_rates = f'sum by (le) (rate({BUCKETS}{labels}[$__rate_interval]))'
        latency = [
            target(f'histogram_quantile({quantile}, {bucket_rates})', name, chr(ord('A') + i))
            for i, (quantile, name) in enumerate([('0.50', 'p50'), ('0.95', 'p95'), ('0.99', 'p99')])
        ]
        rps = f'sum(rate({COUNTER}{labels}[$__rate_interval]))'
        errors = f'sum by (status) (rate({COUNTER}{selector(method, route, errors_only=True)}[$__rate_interval]))'
        y = index * 9
        panels.extend([
            panel(index * 3 + 1, label + ' | p50 / p95 / p99', 0, y, 's', latency),
            panel(index * 3 + 2, label + ' | RPS', 8, y, 'reqps', [target(rps, 'RPS', 'A')]),
            panel(index * 3 + 3, label + ' | errors 4xx / 5xx', 16, y, 'reqps',
                  [target(errors, '{{status}}', 'A')]),
        ])
    return {
        'id': None, 'uid': DASHBOARD_UID,
        'title': 'ITMO TASK1 | HTTP Golden Signals',
        'description': 'Auto-generated from live /handlers; per-handler RPS, 4xx/5xx and aggregated latency.',
        'tags': ['itmo', 'highload', 'task1', 'generated'],
        'schemaVersion': 39, 'version': 0,
        'editable': False,
        'refresh': '5s', 'time': {'from': 'now-15m', 'to': 'now'},
        'timezone': 'browser',
        'templating': {'list': [
            variable('dc', f'label_values({COUNTER}, dc)'),
            variable('pod', f'label_values({COUNTER}{{dc=~"${{dc:regex}}"}}, pod)'),
        ]},
        'panels': panels,
    }


def publish_dashboard(grafana_url: str, username: str, password: str, dashboard: dict) -> str:
    url = grafana_url.rstrip('/')
    source = request_json(url + '/api/datasources/uid/' + GRAFANA_DATASOURCE_UID,
                          username=username, password=password)
    if source.get('type') != 'prometheus' or source.get('uid') != GRAFANA_DATASOURCE_UID:
        raise ValueError('Grafana datasource missing or not Prometheus')
    result = request_json(url + '/api/dashboards/db', method='POST',
                          payload={'dashboard': dashboard, 'overwrite': True,
                                   'message': 'Generated automatically from /handlers'},
                          username=username, password=password)
    if result.get('status') != 'success' or result.get('uid') != DASHBOARD_UID:
        raise ValueError(f'Grafana did not confirm dashboard publication: {result!r}')
    stored = request_json(url + '/api/dashboards/uid/' + DASHBOARD_UID,
                          username=username, password=password)
    saved = stored.get('dashboard', {})
    if saved.get('editable') is not False or len(saved.get('panels', [])) != len(dashboard['panels']):
        raise ValueError('Dashboard API validation failed: editable or panel count mismatch')
    return url + result.get('url', '/d/' + DASHBOARD_UID)


def main() -> int:
    app_urls = [x.strip().rstrip('/') for x in os.getenv('APP_URLS', '').split(',') if x.strip()]
    grafana_url = os.getenv('GRAFANA_URL', 'http://grafana:3000')
    username = os.environ['GRAFANA_ADMIN_USER']
    password = os.environ['GRAFANA_ADMIN_PASSWORD']
    deadline = time.monotonic() + 120
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        try:
            handlers = discover_handlers(app_urls)
            dashboard = build_dashboard(handlers)
            url = publish_dashboard(grafana_url, username, password, dashboard)
            print(f'SUCCESS: discovered {len(handlers)} business handlers, '
                  f'published {len(dashboard["panels"])} panels: {url}', flush=True)
            return 0
        except urllib.error.HTTPError as error:
            if error.code in {400, 401, 403}:
                print(f'FATAL: Grafana rejected request (HTTP {error.code}): {error.reason}',
                      file=sys.stderr, flush=True)
                return 1
            issue = f'HTTP {error.code}'
        except (OSError, ValueError, KeyError, TimeoutError, json.JSONDecodeError) as error:
            issue = str(error)
        print(f'Waiting for Grafana and both apps (attempt {attempt}): {issue}', flush=True)
        time.sleep(3)
    print('FATAL: automatic dashboard generation did not complete within 120s',
          file=sys.stderr, flush=True)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
