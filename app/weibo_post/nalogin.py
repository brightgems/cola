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

Created on 2013-6-8

@author: Chine
'''

import urllib
import base64
import binascii
import re
import json
from cola.core.logs import get_logger
from cola.core.errors import DependencyNotInstalledError,\
                             LoginFailure
from cola.core.opener import SpynnerOpener
from conf import user_config
import random

try:
    import rsa
except ImportError:
    raise DependencyNotInstalledError("rsa")

class WeiboLoginFailure(LoginFailure): pass

class WeiboLogin(object):
    def __init__(self, opener):
        self.opener = opener
        self.logger = get_logger("weibo.login")
        
    def login(self):
        print("**WeiboLogin**")
        uid = random.choice(user_config.job.starts).uid
        
        opener = self.opener
        assert isinstance(opener,SpynnerOpener)
        #opener.br.debug_level=2
        opener.br.embed_jquery=True
        opener.set_default_timeout(30)
        try:
            opener.spynner_open('http://weibo.com/u/%s?is_all=1' % uid,headers=[('User-agent', 'Baiduspider+(+http://www.baidu.com/search/spider.htm)')],
                                wait_for_text = "$CONFIG['page_id']=",tries=2)
            
            self.logger.info("weibo login successfuly bypass account login")
            return(True)			
        except WeiboLoginFailure:
            self.logger.critical("weibo login failed")
            return False
