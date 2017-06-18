#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

Created on 2013-6-7

@author: Chine
'''

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cola.core.urls import Url, UrlPatterns
from cola.job import JobDescription

from parsers import DoubanMovieParser
from conf import starts, user_config, instances, mongo_host, mongo_port, db_name
from cola.core.opener import MechanizeOpener
import random

def login_hook(opener, **kw):

    return True

url_patterns = UrlPatterns(Url('https://movie.douban.com/subject/\d+.*', 'subject', DoubanMovieParser, priority=0),)

def get_job_desc():
    return JobDescription('douban spider', url_patterns, MechanizeOpener, user_config, 
                          starts)
    
if __name__ == "__main__":
    from cola.context import Context
    os.environ.setdefault('http_proxy','')
    ctx = Context(local_mode=True)
    ctx.run_job(os.path.dirname(os.path.abspath(__file__)))