import unittest
from unittest.mock import patch
from fastapi import HTTPException
from server.auth import RateLimit, hash_password, verify_password


class AuthTests(unittest.TestCase):
    def test_password_hash_is_salted_and_preserves_spaces(self):
        a=hash_password(' password with spaces ')
        b=hash_password(' password with spaces ')
        self.assertNotEqual(a,b)
        self.assertTrue(verify_password(' password with spaces ',a))
        self.assertFalse(verify_password('password with spaces',a))

    def test_other_routes_do_not_clear_longer_rate_limit(self):
        rate=RateLimit()
        with patch('server.auth.time.monotonic',return_value=100):
            rate.check('registration',1,3600)
        with patch('server.auth.time.monotonic',return_value=200):
            rate.check('login',10,60)
            with self.assertRaises(HTTPException) as error:
                rate.check('registration',1,3600)
            self.assertEqual(error.exception.status_code,429)
