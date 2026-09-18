import unittest
from unittest.mock import patch
import monitor as m


def rows(prices, offset=0):
    return [[(i + offset) * m.INTERVAL, 0, 0, 0, str(p), 0,
             (i + offset + 1) * m.INTERVAL - 1] for i, p in enumerate(prices)]


class CalculationTests(unittest.TestCase):
    def test_wilder_reference(self):
        prices = [44.34,44.09,44.15,43.61,44.33,44.83,45.10,45.42,45.84,46.08,45.89,46.03,45.61,46.28,46.28,46.00]
        initial, _ = m.advance(None, rows(prices[:15]), 15 * m.INTERVAL)
        self.assertAlmostEqual(m.rsi(initial['gain'], initial['loss']), 70.464135, places=5)
        updated, _ = m.advance(initial, rows(prices[15:], 15), 16 * m.INTERVAL)
        self.assertAlmostEqual(m.rsi(updated['gain'], updated['loss']), 66.249619, places=5)

    def test_every_qualifying_close_and_no_replay(self):
        initial, events = m.advance(None, rows(range(1, 21)), 20 * m.INTERVAL)
        self.assertEqual(len(events), 1)  # Bootstrap only latest.
        updated, events = m.advance(initial, rows([21,22,23], 20), 23 * m.INTERVAL)
        self.assertEqual(len(events), 3)
        self.assertTrue(all(e['rsi'] == 100 for e in events))
        self.assertEqual(m.advance(updated, rows([21,22,23], 20), 23 * m.INTERVAL)[1], [])

    def test_open_candle_excluded(self):
        updated, events = m.advance(None, rows(range(1,22)), 20 * m.INTERVAL)
        self.assertEqual(updated['last_open'], 19 * m.INTERVAL)
        self.assertEqual(events[0]['open'], 19 * m.INTERVAL)

    def test_strict_thresholds(self):
        self.assertFalse(m.qualifies(90))
        self.assertFalse(m.qualifies(15))
        self.assertTrue(m.qualifies(90.00001))
        self.assertTrue(m.qualifies(14.99999))

    def test_down_and_flat(self):
        for prices, expected in [(range(30,10,-1), 0), ([10]*20, 50)]:
            current, events = m.advance(None, rows(prices), 20*m.INTERVAL)
            self.assertEqual(m.rsi(current['gain'], current['loss']), expected)
            self.assertEqual(len(events), int(expected == 0))

    def test_insufficient_history(self):
        self.assertEqual(m.advance(None, rows([1]*14), 14*m.INTERVAL), (None, []))

    def test_gap_keeps_original_state(self):
        initial, _ = m.advance(None, rows(range(1,21)), 20*m.INTERVAL)
        with self.assertRaises(RuntimeError):
            m.advance(initial, rows([22],21), 22*m.INTERVAL)
        self.assertEqual(initial['last_open'], 19*m.INTERVAL)

    def test_paginated_recovery(self):
        initial, _ = m.advance(None, rows(range(1,21)), 20*m.INTERVAL)
        all_rows = rows(range(21,1121), 20)
        def fake(path, **params):
            return [r for r in all_rows if params['startTime'] <= r[0] <= params['endTime']][:params['limit']]
        with patch.object(m, 'binance', side_effect=fake) as mocked:
            updated, events = m.collect('TESTUSDT', initial, 1120*m.INTERVAL)
        self.assertEqual(len(events), 1100)
        self.assertEqual(mocked.call_count, 3)
        self.assertEqual(updated['last_open'], 1119*m.INTERVAL)

    def test_no_request_if_already_current(self):
        initial, _ = m.advance(None, rows(range(1,21)), 20*m.INTERVAL)
        with patch.object(m, 'binance') as mocked:
            updated, events = m.collect('TEST', initial, 20*m.INTERVAL)
        mocked.assert_not_called()
        self.assertEqual(events, [])


if __name__ == '__main__':
    unittest.main()
