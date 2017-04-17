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
import json
import urllib
import re
from datetime import datetime, timedelta
from threading import Lock

from cola.core.parsers import Parser
from cola.core.utils import urldecode, beautiful_soup
from cola.core.errors import DependencyNotInstalledError, FetchBannedError
from cola.core.logs import get_logger
from cola.core.opener import MechanizeOpener,SpynnerOpener

from login import WeiboLoginFailure
from bundle import WeiboUserBundle
from storage import DoesNotExist, Q, WeiboUser, Friend,\
                    MicroBlog, Geo, UserInfo, WorkInfo, EduInfo,\
                    Comment, Forward, Like

from conf import fetch_forward, fetch_comment, fetch_like,fetch_userprofile,effective_start_date

from utils import get_ip_proxy,parse_datetime
from conf import user_config,user_agent
from tools import QT4_Py_Cookie

try:
    from dateutil.parser import parse
except ImportError:
    raise DependencyNotInstalledError('python-dateutil')


TIMEOUT = 30.0

class WeiboParser(Parser):
    def __init__(self, opener=None, url=None, bundle=None, **kwargs):
        super(WeiboParser, self).__init__(opener=opener, url=url, **kwargs)
        self.bundle = bundle
        self.uid = bundle.label
        self.opener.set_default_timeout(TIMEOUT)
        print(user_agent)
        
        if not hasattr(self, 'logger') or self.logger is None:
            self.logger = get_logger(name='weibo_parser')
    
    
    def _check_url(self, dest_url, src_url):
        return dest_url.split('?')[0] == src_url.split('?')[0]
    
    def check(self, url, br):
        dest_url = br.geturl()
        if not self._check_url(dest_url, url):
            if dest_url.startswith('http://weibo.com/login.php'):
                raise WeiboLoginFailure('Weibo not login or login expired')
            if dest_url.startswith('http://weibo.com/sorry?usernotexists'):
                self.bundle.exists = False
                return False
        return True
    
    def get_weibo_user(self):
        if self.bundle.weibo_user is not None:
            return self.bundle.weibo_user
        
        try:
            self.bundle.weibo_user = getattr(WeiboUser, 'objects').get(uid=self.uid)
        except DoesNotExist:
            self.bundle.weibo_user = WeiboUser(uid=self.uid)
            self.bundle.weibo_user.save()
        return self.bundle.weibo_user


class MicroBlogParser(WeiboParser):
    def parse(self, url=None):
        if self.bundle.exists is False:
            return
        
        url = url or self.url
        params = urldecode(url)
        br = self.opener.browse_open(url)
#         self.logger.debug('load %s finish' % url)
        
        if not self.check(url, br):
            return
            
        weibo_user = self.get_weibo_user()
        
        params['_t'] = 0
        params['__rnd'] = str(int(time.time() * 1000))
        page = int(params.get('page', 1))
        pre_page = int(params.get('pre_page', 0))
        count = 15
        if 'pagebar' not in params:
            params['pagebar'] = '0'
            pre_page += 1
        elif params['pagebar'] == '0':
            params['pagebar'] = '1'
        elif params['pagebar'] == '1':
            del params['pagebar']
            pre_page = page
            page += 1
            count = 50
        params['count'] = count
        params['page'] = page
        params['pre_page'] = pre_page

        try:
            data = json.loads(br.response().read())['data']
        except (ValueError, KeyError):
            raise FetchBannedError('fetch banned by weibo server')
        soup = beautiful_soup(data)
        finished = False
        
        divs = soup.find_all('div', attrs={'class': 'WB_feed_type'},  mid=True)
        max_id = None
        for div in divs:
            mid = div['mid']
            if len(mid) == 0:
                continue
            max_id = mid
            blog_create_date = parse(div.select('a.S_link2.WB_time')[0]['title'])
            # skip all following blogs if create date less than effective start
            # date
            if (blog_create_date - effective_start_date).days < 0:
                self.logger.info("%s: blog has sync up after %s" %(self.uid,effective_start_date.strftime("%Y%m%d")))
                finished = True
                break

            if 'end_id' not in params:
                params['end_id'] = mid
            # skip
            if mid in weibo_user.newest_mids:
                self.logger.info("%s: reach earliest blog %s" %(self.uid,mid))
                finished = True
                break
            if len(self.bundle.newest_mids) < 3:
                self.bundle.newest_mids.append(mid)
            
            try:
                mblog = getattr(MicroBlog, 'objects').get(Q(mid=mid) & Q(uid=self.uid))
            except DoesNotExist:
                mblog = MicroBlog(mid=mid, uid=self.uid)
            content_div = div.find('div', attrs={
                'class': 'WB_text', 
                'node-type': 'feed_list_content'
            })
            for img in content_div.find_all("img", attrs={'type': 'face'}):
                img.replace_with(img['title'])
            mblog.content = content_div.text
            is_forward = div.get('isforward')
            if is_forward:
                # write origional user, msg
                mblog.omid = div['omid']
                tbinfos = div['tbinfo'].split('&')
                mblog.ouid = tbinfos[0].split('=')[1]
                name_a = div.find('a', attrs={
                    'class': 'WB_name', 
                    'node-type': 'feed_list_originNick' 
                })
                text_a = div.find('div', attrs={
                    'class': 'WB_text',
                    'node-type': 'feed_list_reason'
                })
                if name_a is not None and text_a is not None:
                    mblog.forward = '%s: %s' % (name_a.text,
                        text_a.text)
            mblog.created = blog_create_date
            mblog.last_update = datetime.now()

            func_div = div.find_all('div', 'WB_func')[-1]
            action_type_re = lambda t: re.compile("^(feed_list|fl)_%s$" % t)
            
            likes = func_div.find('a', attrs={'action-type': action_type_re("like")}).text
            likes = likes.strip('(').strip(')')
            likes = 0 if len(likes) == 0 else int(likes)
            mblog.n_likes = likes
            forwards = func_div.find('a', attrs={'action-type': action_type_re("forward")}).text
            if '(' not in forwards:
                mblog.n_forwards = 0
            else:
                mblog.n_forwards = int(forwards.strip().split('(', 1)[1].strip(')'))
            comments = func_div.find('a', attrs={'action-type': action_type_re('comment')}).text
            if '(' not in comments:
                mblog.n_comments = 0
            else:
                mblog.n_comments = int(comments.strip().split('(', 1)[1].strip(')'))
                
            # fetch geo info
            map_info = div.find("div", attrs={'class': 'map_data'})
            if map_info is not None:
                geo = Geo()
                geo.location = map_info.text.split('-')[0].strip()
                geo_info = urldecode("?" + map_info.find('a')['action-data'])['geo']
                geo.longtitude, geo.latitude = tuple([float(itm) for itm in geo_info.split(',', 1)])
                mblog.geo = geo
            
            mblog.save()
        
        if 'pagebar' in params:
            params['max_id'] = max_id
        else:
            del params['max_id']
#         self.logger.debug('parse %s finish' % url)

        # counter add one for the processed weibo list url
        self.counter.inc('processed_weibo_list_page', 1)

        # if not has next page
        if len(divs) == 0 or finished:
            weibo_user = self.get_weibo_user()
            for mid in self.bundle.newest_mids:
                if mid not in weibo_user.newest_mids:
                    weibo_user.newest_mids.append(mid)
            while len(weibo_user.newest_mids) > 3:
                weibo_user.newest_mids.pop()
            weibo_user.last_update = self.bundle.last_update
            weibo_user.save()
            return

        yield '%s?%s' % (url.split('?')[0], urllib.urlencode(params))
    