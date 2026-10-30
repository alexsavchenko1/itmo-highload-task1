import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import dashboard_generator as d


class DashboardGenerationTest(unittest.TestCase):
    HANDLERS = [
        ('POST', '/items'),
        ('GET', '/items/{id}'),
        ('PUT', '/items/{id}'),
    ]

    def test_dynamic_routes_and_promql(self):
        db = d.build_dashboard(self.HANDLERS)
        self.assertFalse(db['editable'])
        self.assertEqual(len(db['panels']), 9)
        vars_ = {v['name'] for v in db['templating']['list']}
        self.assertEqual(vars_, {'dc', 'pod'})
        self.assertEqual({p['title'].split(' | ')[0] for p in db['panels']},
                         {'POST /items', 'GET /items/{id}', 'PUT /items/{id}'})
        for i in range(0, 9, 3):
            latency, rps, errors = db['panels'][i:i + 3]
            self.assertEqual(len(latency['targets']), 3)
            for t in latency['targets']:
                self.assertIn('sum by (le) (rate(', t['expr'])
                self.assertIn('dc=~"${dc:regex}"', t['expr'])
                self.assertIn('pod=~"${pod:regex}"', t['expr'])
            self.assertIn('sum(rate(', rps['targets'][0]['expr'])
            self.assertIn('status=~"4..|5.."', errors['targets'][0]['expr'])
            self.assertIn('sum by (status)', errors['targets'][0]['expr'])

    def test_added_handler_creates_more_panels(self):
        db = d.build_dashboard(self.HANDLERS + [('DELETE', '/items/{id}')])
        self.assertEqual(len(db['panels']), 12)

    def test_discovery_filters_only_technical_paths(self):
        sample = [{'method': 'GET', 'route': path} for path in
                  ('/metrics', '/health', '/handlers', '/error', '/items/{id}')]
        sample.append({'method': 'POST', 'route': '/items'})
        with patch.object(d, 'request_json', return_value=sample) as fn:
            result = d.discover_handlers(['http://app-1:8080', 'http://app-2:8080'])
        self.assertEqual(result, [('POST', '/items'), ('GET', '/items/{id}')])
        self.assertEqual(fn.call_count, 2)

    def test_no_handler_catalog_hardcoded(self):
        sample = [{'method': 'PATCH', 'route': '/new/{id}'}]
        with patch.object(d, 'request_json', return_value=sample):
            handlers = d.discover_handlers(['http://app-1:8080'])
        db = d.build_dashboard(handlers)
        self.assertEqual(len(db['panels']), 3)
        self.assertTrue(all('PATCH /new/{id}' in p['title'] for p in db['panels']))

    def test_publish_checks_grafana_api_result(self):
        generated = d.build_dashboard(self.HANDLERS)
        replies = [
            {'type': 'prometheus', 'uid': 'itmo-prometheus'},
            {'status': 'success', 'uid': 'itmo-items-golden-signals', 'url': '/d/itmo-items-golden-signals'},
            {'dashboard': generated},
        ]
        with patch.object(d, 'request_json', side_effect=replies) as sender:
            url = d.publish_dashboard('http://grafana:3000', 'admin', 'test-secret', generated)
        self.assertEqual(url, 'http://grafana:3000/d/itmo-items-golden-signals')
        self.assertEqual(sender.call_count, 3)
        self.assertEqual(sender.call_args_list[1].kwargs['method'], 'POST')
        self.assertTrue(sender.call_args_list[1].kwargs['payload']['overwrite'])

    def test_technical_route_is_never_a_business_panel(self):
        self.assertEqual(d.TECHNICAL_ROUTES,
                         {'/metrics', '/handlers', '/health', '/error'})


if __name__ == '__main__':
    unittest.main()
