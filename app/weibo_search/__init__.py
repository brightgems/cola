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

Created on 2013-6-27

@author: Chine
'''

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cola.core.opener import SpynnerOpener
from cola.core.urls import Url, UrlPatterns
from cola.job import JobDescription
from cola.core.opener import MechanizeOpener

from login import WeiboLogin
from parsers import WeiboSearchParser, UserHomePageParser
from conf import user_config, instances
from bundle import WeiboSearchBundle
from conf import starts, user_config, instances

def login_hook(opener, **kw):
    username = kw['username']
    passwd = kw['password']
    
    loginer = WeiboLogin(opener, username, passwd)
    return loginer.login()

url_patterns = UrlPatterns(
    Url(u'http://s.weibo.com/weibo/.*', 'weibo_search', WeiboSearchParser, priority=0),
    Url(u'http://weibo.com/\d+\?.*', 'user_home', UserHomePageParser, priority=0),
)

def get_job_desc():
    return JobDescription('weibo search', url_patterns, MechanizeOpener, user_config, 
                          starts, unit_cls=WeiboSearchBundle, login_hook=login_hook)
    
if __name__ == "__main__":
    from cola.context import Context
    ctx = Context(local_mode=True)
    ctx.run_job(os.path.dirname(os.path.abspath(__file__)))