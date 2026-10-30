
import collections
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import load_generator as g


class LoadTest(unittest.TestCase):
    def test_ramp_is_monotone_and_reaches_target(self):
        self.assertEqual(g.target_rps(0, 3, 40, 120), 3)
        self.assertAlmostEqual(g.target_rps(60, 3, 40, 120), 21.5)
        self.assertEqual(g.target_rps(120, 3, 40, 120), 40)
        self.assertEqual(g.target_rps(999, 3, 40, 120), 40)

    def test_two_replicas_separate_memory_and_404_500(self):
        load = g.Load(['http://app-1:8080', 'http://app-2:8080'])
        load.ids[load.urls[0]].append(11)
        load.ids[load.urls[1]].append(55)

        url, method, path, body, synthetic = load.choose_request(0)
        self.assertEqual(url, 'http://app-1:8080')
        self.assertEqual((method, path, synthetic), ('POST', '/items', True))

        # Обычные запросы используют память своего экземпляра.
        self.assertEqual(load.choose_request(1)[2], '/items/55')
        self.assertEqual(load.choose_request(2)[2], '/items/11')
        url, method, path, _, synthetic = load.choose_request(3)
        self.assertEqual(url, 'http://app-2:8080')
        self.assertIn('55', path)
        self.assertFalse(synthetic)

        # Ошибки 404 и 500 должны появляться на обоих экземплярах.
        self.assertEqual(
            load.choose_request(25)[:3],
            ('http://app-2:8080', 'GET', '/items/987654321')
        )
        self.assertEqual(
            load.choose_request(50)[:3],
            ('http://app-1:8080', 'GET', '/items/987654321')
        )
        self.assertEqual(load.choose_request(75)[0], 'http://app-2:8080')
        self.assertTrue(load.choose_request(75)[4])

    def test_four_percent_intentional_errors_across_both_replicas(self):
        load = g.Load(['http://app-1:8080', 'http://app-2:8080'])
        load.ids[load.urls[0]].append(11)
        load.ids[load.urls[1]].append(55)

        errors = collections.Counter()

        for sequence in range(100):
            url, method, path, body, synthetic = load.choose_request(sequence)

            if synthetic:
                errors[(url, 500)] += 1
            elif method == 'GET' and path == '/items/987654321':
                errors[(url, 404)] += 1

            self.assertNotEqual(body, {'name': ''})

        self.assertEqual(errors, collections.Counter({
            ('http://app-1:8080', 500): 1,
            ('http://app-1:8080', 404): 1,
            ('http://app-2:8080', 500): 1,
            ('http://app-2:8080', 404): 1,
        }))
        self.assertEqual(sum(errors.values()), 4)

    def test_successful_create_tracks_id_in_its_own_pod(self):
        load = g.Load(['http://app-1:8080', 'http://app-2:8080'])

        with patch.object(
            load,
            'choose_request',
            return_value=(
                load.urls[0],
                'POST',
                '/items',
                {'name': 'x'},
                False
            )
        ):
            with patch.object(
                load,
                'send',
                return_value=(201, {'id': 123})
            ):
                load.send_one(50)

        self.assertIn(123, load.ids[load.urls[0]])
        self.assertFalse(load.ids[load.urls[1]])
        self.assertEqual(load.status_counts['201'], 1)


if __name__ == '__main__':
    unittest.main()
