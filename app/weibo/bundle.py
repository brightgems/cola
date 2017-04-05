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

import time

from cola.core.unit import Bundle
from conf import fetch_userprofile

class WeiboUserBundle(Bundle):
    def __init__(self, uid):
        super(WeiboUserBundle, self).__init__(uid)
        self.uid = uid
        self.pid = None
        self.domain = None
        self.exists = True
        
        self.last_error_page = None
        self.last_error_page_times = 0
        
        self.weibo_user = None
        self.last_update = None
        self.newest_mids = []
        self.current_mblog = None
        
    def urls(self):
        start = int(time.time() * (10 ** 6))
        urls_ = [
            # 微博主页
            'http://weibo.com/%s?is_all=1&_k=%s' % (self.uid, start),
        ]
        if fetch_userprofile:
            urls.append('http://weibo.com/%s/info' % self.uid) # only apply for personal account
            urls.append('http://weibo.com/%s/follow' % self.uid)
        return urls_