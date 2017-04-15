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

from nalogin import WeiboLogin as NoAccountLogin
from login import WeiboLogin as AccountLogin
from parsers import MicroBlogParser, ForwardCommentLikeParser,\
                    UserInfoParser, UserFriendParser
from conf import starts, user_config, instances
from bundle import WeiboUserBundle
from cola.core.opener import MechanizeOpener,SpynnerOpener
import random
from tools import QT4_Py_Cookie
from cookielib import MozillaCookieJar

def login_hook(opener, **kw):
    username = str(kw['username'])
    passwd = str(kw['password'])
    # Skip login step if detail user profile doesn't need
    if not getattr(user_config.job.fetch,"userprofile",False):
        qtbr = SpynnerOpener(user_agent= user_config.conf.opener.user_agent)
        loginer = NoAccountLogin(qtbr)
        ret = loginer.login()
        # copy cookie jar to opener
        cv = QT4_Py_Cookie()
        cj = MozillaCookieJar()
        cv.toPyCookieJar(qtbr.br.cookiejar,cj)
        opener.cj = cj
        opener.qtcj = qtbr.br.cookiejar
        opener.browser.set_cookiejar(cj)
        opener.browser.addheaders = [('User-agent', user_config.conf.opener.user_agent)]
    else:
        loginer = AccountLogin(opener)
        ret = loginer.login()
    return ret

url_patterns = UrlPatterns(Url('http://weibo.com/p/aj/v6/mblog/mbloglist.*', 'micro_blog', MicroBlogParser, priority=1),
    Url(r'http://weibo.com/aj/.+/big.*', 'forward_comment_like', ForwardCommentLikeParser ,priority=2),
    Url(r'http://weibo.com/p/\d+/info', 'user_info', UserInfoParser,priority=1),
    Url(r'http://weibo.com/\d+/follow.*', 'follows', UserFriendParser,priority=2),
    Url(r'http://weibo.com/\d+/fans.*', 'fans', UserFriendParser,priority=2),)

def get_job_desc():
    return JobDescription('sina weibo crawler', url_patterns, MechanizeOpener, user_config, 
                          starts,unit_cls=WeiboUserBundle, login_hook=login_hook)
    
if __name__ == "__main__":
    from cola.context import Context
    ctx = Context(local_mode=True)
    ctx.run_job(os.path.dirname(os.path.abspath(__file__)))