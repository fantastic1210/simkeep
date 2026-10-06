import unittest

try:
    from server import domain
except ImportError:
    domain = None


class DomainTests(unittest.TestCase):
    def run_function(self, name, *args):
        self.assertIsNotNone(domain, 'Service date rules must be implemented')
        return getattr(domain, name)(*args)

    def test_calendar_months_and_leap_year(self):
        self.assertEqual(self.run_function('add_cycle','2026-01-31',1,'months'),'2026-02-28')
        self.assertEqual(self.run_function('add_cycle','2028-01-31',1,'months'),'2028-02-29')

    def test_fixed_months_restore_original_anchor(self):
        rule = dict(dueDate='2026-02-28',anchorDate='2026-01-31',interval=1,unit='months',anchor='scheduled')
        self.assertEqual(self.run_function('next_due',rule,'2026-02-28'),'2026-03-31')

    def test_early_fixed_completion_advances_current_occurrence(self):
        rule = dict(dueDate='2026-10-10',anchorDate='2026-10-10',interval=1,unit='months',anchor='scheduled')
        self.assertEqual(self.run_function('next_due',rule,'2026-10-04'),'2026-11-10')

    def test_overdue_fixed_completion_skips_elapsed_occurrences(self):
        rule = dict(dueDate='2026-01-31',anchorDate='2026-01-31',interval=1,unit='months',anchor='scheduled')
        self.assertEqual(self.run_function('next_due',rule,'2026-04-01'),'2026-04-30')

    def test_completion_based_dates_start_from_actual_date(self):
        rule = dict(dueDate='2026-10-03',interval=90,unit='days',anchor='completion')
        self.assertEqual(self.run_function('next_due',rule,'2026-10-04'),'2027-01-02')

    def test_bad_date_and_cycle_rejected(self):
        self.assertIsNotNone(domain)
        for value, interval, unit in [('2026-02-30',1,'months'),('2026-10-04',0,'days'),('2026-10-04',True,'days')]:
            with self.assertRaises(ValueError):
                domain.add_cycle(value,interval,unit)


if __name__ == '__main__':
    unittest.main()
