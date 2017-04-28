# coding: utf8
import unittest
from cola.utilities.util_fetch import get_ip_proxy
from cola.utilities.util_parse import parse_datetime
from datetime import datetime

class Test(unittest.TestCase):
    def test_get_ip_proxy(self):
        p_ = get_ip_proxy()
        self.assertIsNotNone(p_)

    def test_parse_datetime(self):
        from datetime import datetime
        at = parse_datetime(u'今天 09:08')
        ep = datetime.strptime(datetime.today().strftime('%Y%m%d') + ' 09:08','%Y%m%d %H:%M')
        self.assertEqual(at,ep)
        parse_datetime(u'2008年9月9日')
        ep = datetime.datetime(2008,9,9)
        self.assertEqual(at,ep)
        

if __name__ == '__main__':
    unittest.main()
