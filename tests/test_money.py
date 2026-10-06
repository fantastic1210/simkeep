import unittest

try:
    from server.money import normalize_amount, apply_balance
except ImportError:
    normalize_amount = apply_balance = None


class MoneyTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(normalize_amount,'Exact multi-currency amounts must be implemented')

    def test_normalizes_currency_precision_without_rounding(self):
        self.assertEqual(normalize_amount('00019.9','USD'),'19.90')
        self.assertEqual(normalize_amount('1000.00','JPY'),'1000')
        self.assertEqual(normalize_amount('1.234','KWD'),'1.234')
        self.assertEqual(normalize_amount('0','GBP'),'0.00')

    def test_invalid_amounts_are_rejected(self):
        for amount,currency in [('1.001','USD'),('0.1','JPY'),('-1','USD'),('NaN','USD'),('1e3','USD'),('1000000000','USD'),('1','ZZZ')]:
            with self.subTest(amount=amount,currency=currency),self.assertRaises(ValueError):
                normalize_amount(amount,currency)

    def test_exact_subtraction_only_touches_matching_currency(self):
        balances=[{'currency':'USD','amount':'0.30'},{'currency':'GBP','amount':'8.00'}]
        updated,before,after=apply_balance(balances,{'currency':'USD','amount':'0.10'},'deduct')
        self.assertEqual(updated,[{'currency':'USD','amount':'0.20'},{'currency':'GBP','amount':'8.00'}])
        self.assertEqual(before,{'currency':'USD','amount':'0.30'})
        self.assertEqual(after,{'currency':'USD','amount':'0.20'})
        self.assertEqual(balances[0]['amount'],'0.30')

    def test_insufficient_or_missing_balance_cannot_be_deducted(self):
        for balances,cost in [([],{'currency':'USD','amount':'1.00'}),([{'currency':'USD','amount':'1.00'}],{'currency':'USD','amount':'1.01'})]:
            with self.assertRaises(ValueError):
                apply_balance(balances,cost,'deduct')

    def test_topup_can_create_currency_and_credit_exactly(self):
        balances=[{'currency':'JPY','amount':'100'}]
        updated,before,after=apply_balance(balances,{'currency':'HKD','amount':'10.50'},'credit')
        self.assertEqual(updated,[{'currency':'JPY','amount':'100'},{'currency':'HKD','amount':'10.50'}])
        self.assertEqual(before,{'currency':'HKD','amount':'0.00'})
        self.assertEqual(after,{'currency':'HKD','amount':'10.50'})
