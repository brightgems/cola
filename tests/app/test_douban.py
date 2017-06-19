# coding: utf-8
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

Created on 2017-6/16

@author: brtgpy
'''
import unittest
from datetime import datetime

from app.douban_movie import DoubanMovieParser, url_patterns, \
                         mongo_host, mongo_port, db_name

class Test(unittest.TestCase):


    def testDoubanMovieParser(self):
        parser = DoubanMovieParser()
        url = 'https://movie.douban.com/subject/2224146/'
        parser.parse(url)
        
        from pymongo import MongoClient
        conn = MongoClient(mongo_host, mongo_port)
        db = getattr(conn, db_name)
        movie = db.douban_movie.find_one({'sid': '2224146'})
        self.assertIsNotNone(movie)
        self.assertTrue(movie['casts'] != [])
        print(movie)
        #db.douban_movie.remove({'title': u'红楼梦'})
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()