import unittest
from cola.utilities.util_fetch import get_ip_proxy

class Test(unittest.TestCase):
    def test_get_ip_proxy(self):
        p_= get_ip_proxy()
        self.assertIsNotNone(p_)

if __name__ == '__main__':
    unittest.main()
