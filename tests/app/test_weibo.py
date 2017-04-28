# coding: utf8
'''
Copyright (c) 2013 Qin Xuye <qin@qinxuye.me>

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Created on 2013-6-10

@author: Chine
'''
import unittest
import time

import os
import sys

sys.path.insert(0,os.path.curdir)

from cola.core.opener import SpynnerOpener,MechanizeOpener
from cola.core.unit import Bundle

from app.weibo import login_hook
from app.weibo.parsers import MicroBlogParser, ForwardCommentLikeParser, \
                                    UserInfoParser, UserFriendParser,UserHomePageParser
from app.weibo.conf import user_config
from app.weibo.bundle import WeiboUserBundle

from pymongo import MongoClient
from app.weibo.tools import QT4_Py_Cookie

from cookielib import MozillaCookieJar

class Test(unittest.TestCase):


    def setUp(self):
        self.test_uid = '1667486960'
        self.bundle = WeiboUserBundle(self.test_uid)
        self.opener = MechanizeOpener()
        
        self.conn = MongoClient()
        self.db = self.conn[getattr(user_config.job, 'db')]
        self.users_collection = self.db.weibo_user
        self.weibos_collection = self.db.micro_blog
        
        #assert len(user_config.job['login']) > 0
        
        login_hook(self.opener, **user_config.job['login'][0])

    def _get_urls_and_bundles(self, yields):
        urls = []
        bundles = []
        for item in yields:
            if isinstance(item, Bundle):
                bundles.append(item)
            else:
                urls.append(item)
        return urls, bundles

    def tearDown(self):
        self.users_collection.remove({'uid': self.test_uid})
        self.weibos_collection.remove({'uid': self.test_uid})
        self.conn.close()
        
    def testMicroBlogParser(self):
        test_url = 'http://weibo.com/p/aj/v6/mblog/mbloglist?ajwvr=6&domain=100606&is_hot=1&pl_name=Pl_Official_MyProfileFeed__24&id=1006063949575070&script_uri=/u/3949575070&feed_type=1&page=1&pre_page=1&domain_op=100606&__rnd=%d' % (
            #self.test_uid,
            int(time.time() * (10**6))
        )
        parser = MicroBlogParser(opener=self.opener, 
                                 url=test_url, 
                                 bundle=self.bundle)
        _, bundles = self._get_urls_and_bundles(parser.parse())
           
        self.assertEqual(len(bundles), 0)
            
        size = self.weibos_collection.find({'uid': self.test_uid}).count()
        self.assertAlmostEqual(size, 15, delta=1)

    def testUserHomePageParser(self):
        test_url = 'http://weibo.com/%s?is_all=1&_k=%s' % (
            self.test_uid,
            int(time.time() * (10**6))
        )
        print(self.opener.cj._cookies)
        parser = UserHomePageParser(opener=self.opener, 
                                 url=test_url, 
                                 bundle=self.bundle)
        urls, bundles = self._get_urls_and_bundles(parser.parse())
           
        self.assertEqual(len(urls), 1)
        print(urls)
         
        
    def testMicroBlogForwardsParser(self):
        
        test_url = 'http://weibo.com/aj/mblog/info/big?ajwvr=6&_t=0&from=singleWeiBo&id=4088805093057594&__rnd=1491471906078'
        parser = ForwardCommentLikeParser(opener=self.opener,
                                          url=test_url,
                                          bundle=self.bundle)
        urls, _ = self._get_urls_and_bundles(parser.parse())
        
        self.assertEqual(len(urls), 1)
        
        weibo = self.weibos_collection.find_one({'mid': '3596988739933218', 'uid': self.test_uid})
        self.assertLessEqual(len(weibo['forwards']), 20)
        self.assertGreater(len(weibo['forwards']), 0)
        
        parser.parse(urls[0])
        weibo = self.weibos_collection.find_one({'mid': '3596988739933218', 'uid': self.test_uid})
        self.assertLessEqual(len(weibo['forwards']), 40)
        self.assertGreater(len(weibo['forwards']), 10)
        self.assertNotEqual(weibo['forwards'][0], 
                            weibo['forwards'][10])
        
    def testMicroBlogLikesParser(self):
        test_url = 'http://weibo.com/aj/like/big?ajwvr=6&mid=3599246068109415&_t=0&__rnd=1373634556882'
        parser = ForwardCommentLikeParser(opener=self.opener,
                                          url=test_url,
                                          bundle=self.bundle)
        urls, _ = self._get_urls_and_bundles(parser.parse())
        
        self.assertEqual(len(urls), 1)
        
        weibo = self.weibos_collection.find_one({'mid': '3599246068109415', 'uid': self.test_uid})
        self.assertEqual(len(weibo['likes']), 30)
  
    def testUserInfoParser(self):
        test_url = 'http://weibo.com/%s/info' % self.test_uid
        parser = UserInfoParser(opener=self.opener,
                                url=test_url,
                                bundle=self.bundle)
        parser.parse()
            
        user = self.users_collection.find_one({'uid': self.test_uid})
        self.assertTrue('info' in user)
         
    def testUserInfoParserForSite(self):
        test_uid = '2733272463'
        test_url = 'http://weibo.com/%s/info' % test_uid
        bundle = WeiboUserBundle(test_uid)
        parser = UserInfoParser(opener=self.opener,
                                url=test_url,
                                bundle=bundle)
        parser.parse()
         
    def testFriendParser(self):
        test_url = 'http://weibo.com/%s/follow' % self.test_uid
        parser = UserFriendParser(opener=self.opener,
                                  url=test_url,
                                  bundle=self.bundle)
        urls, bundles = self._get_urls_and_bundles(parser.parse())
        self.assertEqual(len(urls), 1)
        self.assertGreater(bundles, 0)
          
        user = self.users_collection.find_one({'uid': self.test_uid})
        self.assertEqual(len(bundles), len(user['follows']))


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testParser']
    unittest.main()