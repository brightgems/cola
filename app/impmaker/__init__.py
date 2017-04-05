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

Created on 2017-3-24

@author: brtg
'''

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import urlparse

from cola.core.urls import UrlPatterns, Url
from cola.core.parsers import Parser
from cola.core.opener import MechanizeOpener
from cola.core.errors import DependencyNotInstalledError
from cola.core.config import Config
from cola.core.extractor import Extractor
from cola.core.extractor.utils import host_for_url
from cola.job import JobDescription
import random
import time
from utils import get_ip_proxy,random_user_agent

get_user_conf = lambda s: os.path.join(os.path.dirname(os.path.abspath(__file__)), s)
user_conf = get_user_conf('impmaker.yaml')

user_config = Config(user_conf)

starts = [start.url for start in user_config.job.starts]


class ImpMakerParser(Parser):
    def __init__(self, opener=None, url=None, **kw):
        super(ImpMakerParser, self).__init__(opener=opener, url=url, **kw)
        self.logger = kw.get('logger')
   
    def parse(self, url=None):
        url = url or self.url
        if 'click' not in url:
            times = random.randrange(2,5)
        else:
            times = 1
        i = 0
        
        self.opener = MechanizeOpener(user_agent=random_user_agent())
        odds = random.randint(0,100)
        if 'click' not in url or odds <= 5:
            # add proxy
            p_ = get_ip_proxy()
            if p_:
                
                self.opener.remove_proxy()
                self.opener.add_proxy(p_)
            while i < times:
                html = self.opener.open(url)
                #print(html)
                i = i + 1
                time.sleep(.1)
 
        return url
    
def get_job_desc():
    urls = []
    for pattern in user_config.job.patterns:
        url_pattern = Url(pattern.regex, pattern.name, ImpMakerParser,priority=1)
        urls.append(url_pattern)
    url_patterns = UrlPatterns(*urls)
    
    return JobDescription(user_config.job.name, url_patterns, MechanizeOpener, user_config, 
                          starts, unit_cls=None, login_hook=None)
    
if __name__ == "__main__":
    from cola.context import Context
    ctx = Context(local_mode=True)
    ctx.run_job(os.path.dirname(os.path.abspath(__file__)))