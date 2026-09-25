from django.test import SimpleTestCase

from espcontrol import who_air


class WhoAirTests(SimpleTestCase):
    def test_pm25_levels_follow_who_2021(self):
        expected = [(4.7, "excellent"), (5, "excellent"), (5.1, "bon"), (15, "bon"),
                    (15.1, "modere"), (25, "modere"), (37.5, "mediocre"),
                    (75, "mauvais"), (75.1, "dangereux")]
        for value, key in expected:
            self.assertEqual(who_air.classify("pm2p5", value)["key"], key, value)

    def test_pm10_levels_follow_who_2021(self):
        expected = [(15, "excellent"), (45, "bon"), (75, "modere"),
                    (100, "mediocre"), (200, "mauvais"), (200.1, "dangereux")]
        for value, key in expected:
            self.assertEqual(who_air.classify("pm10", value)["key"], key, value)

    def test_no_value_gives_no_level(self):
        self.assertIsNone(who_air.classify("pm2p5", None))
        self.assertIsNone(who_air.classify("pm2p5", "abc"))

    def test_report_ignores_single_spike_and_takes_worst_pollutant(self):
        recent = [{"pm2p5": 200, "pm10": 4.7}, {"pm2p5": 4.7, "pm10": 4.7},
                  {"pm2p5": 4.6, "pm10": 4.6}, {"pm2p5": 4.8, "pm10": 4.8},
                  {"pm2p5": 4.7, "pm10": 4.7}]
        report = who_air.device_report(recent, 6.0, 6.0)
        self.assertEqual(report["overall"]["key"], "excellent")
        self.assertFalse(report["pm2p5"]["avg24_ok"] is False)

    def test_equal_pm_gives_full_fine_fraction(self):
        report = who_air.device_report([{"pm2p5": 4.7, "pm10": 4.7}], 4.7, 4.7)
        self.assertEqual(report["fine_ratio"], 100)
        self.assertEqual(report["coarse"], 0)

    def test_exceedance_flag(self):
        report = who_air.device_report([{"pm2p5": 30, "pm10": 30}], 30, 30)
        self.assertFalse(report["pm2p5"]["avg24_ok"])
        self.assertTrue(report["pm10"]["avg24_ok"])
