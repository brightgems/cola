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

import urlparse
import urllib

from cola.core.parsers import Parser
from cola.core.errors import DependencyNotInstalledError

from bundle import WeiboSearchBundle
from storage import MicroBlog, DoesNotExist, Q

try:
    from bs4 import BeautifulSoup
except ImportError:
    raise DependencyNotInstalledError('BeautifulSoup4')

try:
    from dateutil.parser import parse
except ImportError:
    raise DependencyNotInstalledError('python-dateutil')

try:
    from spynner import SpynnerTimeout
except ImportError:
    raise DependencyNotInstalledError('spynner')

class WeiboSearchParser(Parser):
    def __init__(self, opener=None, url=None, bundle=None, **kwargs):
        super(WeiboSearchParser, self).__init__(opener=opener, url=url, **kwargs)
        self.bundle = bundle
        self.keyword = bundle.label
        
    def get_weibo(self, mid, keyword):
        try:
            weibo = getattr(MicroBlog, 'objects').get(Q(mid=mid) & Q(keyword=keyword))
            return weibo, True
        except DoesNotExist:
            weibo = MicroBlog(mid=mid, keyword=keyword)
            weibo.save()
            return weibo, False
        
    def parse(self, url=None):
        url = url or self.url
        
        br = self.opener.spynner_open(url)
        self.opener.wait_for_selector('div#pl_weibo_feedlist')
        try:
            self.opener.wait_for_selector('div.feed_lists', tries=5)
        except SpynnerTimeout:
            bundle = WeiboSearchBundle(self.keyword, force=True)
            return [], [bundle]
            
        html = br.html
        soup = BeautifulSoup(html)
        
        finished = False
        
        dls = soup.find_all('dl', attrs={'class': 'feed_list'}, mid=True)
        for dl in dls:
            mid = dl['mid']
            weibo, finished = self.get_weibo(mid, self.keyword)
            
            if finished:
                break
            
            weibo.content = dl.find('p', attrs={'node-type': 'feed_list_content'}).text.strip()
            is_forward = dl.get('isforward') == '1'
            if is_forward:
                weibo.forward = dl.find(
                    'dt', attrs={'node-type': 'feed_list_forwardContent'}).text.strip()
            p = dl.select('p.info.W_linkb.W_textb')[0]
            weibo.created = parse(p.find('a', attrs={'class': 'date'})['title'])
            likes = p.find('a', attrs={'action-type': 'feed_list_like'}).text
            if '(' not in likes:
                weibo.likes = 0
            else:
                weibo.likes = int(likes.strip().split('(', 1)[1].strip(')'))
            forwards = p.find('a', attrs={'action-type': 'feed_list_forward'}).text
            if '(' not in forwards:
                weibo.forwards = 0
            else:
                weibo.forwards = int(forwards.strip().split('(', 1)[1].strip(')'))
            comments = p.find('a', attrs={'action-type': 'feed_list_comment'}).text
            if '(' not in comments:
                weibo.comments = 0
            else:
                weibo.comments = int(comments.strip().split('(', 1)[1].strip(')'))
                
            weibo.save()
            
        pages = soup.find('div', attrs={'class': 'search_page'})
        if pages is None or len(list(pages.find_all('a'))) == 0:
            finished = True
        else:
            next_page = pages.find_all('a')[-1]
            if next_page.text.strip() == u'下一页':
                next_href = next_page['href']
                if not next_href.startswith('http://'):
                    next_href = urlparse.urljoin('http://s.weibo.com', next_href)
                    url, query = tuple(next_href.split('&', 1))
                    base, key = tuple(url.rsplit('/', 1))
                    key = urllib.unquote(key)
                    url = '/'.join((base, key))
                    next_href = '&'.join((url, query))
                return [next_href], []
            else:
                finished = True
        
        if finished:
            bundle = WeiboSearchBundle(self.keyword, force=True)
            return [], [bundle]
        return [], []

class UserHomePageParser(WeiboParser):
    def extract_user_info(self,soup,weibo_user):
        div_pi = soup.find('div',attrs={'class','PCD_person_info'})
        # verfiy cop
        bs_verify = div_pi.find('a',attrs={'class':'icon_verify_co_v'})
        weibo_user.info.is_person = False if bs_verify else True
        
        # vip person
        bs_vip = div_pi.find('a',attrs={'class':'icon_verify_v'})
        weibo_user.info.vip = True if bs_vip else False
        weibo_user.info.verified = True if bs_verify or bs_vip else False
        weibo_user.info.level = int(div_pi.find('a',attrs={'class':'W_icon_level'}).text.split('.')[1])

    def extract_user_counter(self,soup,weibo_user):       
        # msg counter
        tds = soup.find('table', attrs={'class': 'tb_counter'}).find_all('td')

        if tds:
            weibo_user.info.n_follows = int(tds[0].find('strong').text)
            weibo_user.info.n_fans = int(tds[1].find('strong').text)
            weibo_user.info.n_msgs = int(tds[2].find('strong').text)


    def parse(self, url=None):
        if self.bundle.exists is False:
            return
        url = url or self.url
        html = ''
        opener = None
        
        try:
            #if hasattr(self.opener,'nalbr'):
            #    opener = self.opener.nalbr # no account login browser
            #else:
            #    opener = MechanizeOpener(timeout=10,user_agent=user_config.conf.opener.user_agent)
                
            #    p_ = get_ip_proxy()
            #    self.logger.info(p_)
            #    opener.add_proxy(p_,'http')
            #    self.opener.nalbr = opener
            opener = self.opener
            opener.addheaders=[('User-Agent',user_config.conf.opener.user_agent)]
            html = to_unicode(opener.open(url,timeout=10))
            
            opener.browser.clear_history() # resolve memory issue
        except Exception, ex:
            
            if opener:
                opener.browser.close()
            raise Exception("get banned on user page")
        

        if not html:
            return

        soup = beautiful_soup(html)
        weibo_user = self.get_weibo_user()
        if weibo_user.info is None:
            weibo_user.info = UserInfo()

        # find page_id
        try:
            pid_ = re.findall("CONFIG\['page_id'\]='(.*)';",html)[0]
        except:
            if opener:
                opener.browser.close()
            if hasattr(self.opener,'nalbr'):
                del self.opener.nalbr

            raise FetchBannedError("get banned on user page")

        domain_ = re.findall("CONFIG\['domain'\]='(.*)';",html)[0]

        for script in soup.find_all('script'):
            text = script.text
            if text.startswith('FM.view'):
                text = text.strip().replace(';', '').replace('FM.view(', '')[:-1]
                data = json.loads(text)
                domid = data['domid']
                if domid.startswith("Pl_Core_UserInfo"):
                    header_soup = beautiful_soup(data['html'])
                    self.extract_user_info(header_soup,weibo_user)
                elif domid.startswith("Pl_Official_Header"):  
                    header_soup = beautiful_soup(data['html'])
                    # nickname
                    nickname_ = header_soup.find('div',attrs={'class','pf_username'}).text
                elif domid.startswith("Pl_Core_T8CustomTriColumn"):  
                    header_soup = beautiful_soup(data['html'])
                    self.extract_user_counter(header_soup,weibo_user)

        self.bundle.pid = pid_
        self.bundle.domain = domain_
        weibo_user.pid = pid_
        weibo_user.info.domain = domain_
        weibo_user.info.nickname = nickname_.strip()
        weibo_user.save()

        # counter add one for the processed user home list url
        self.counter.inc('processed_weibo_user_home_page', 1)
        time.sleep(1)
        if fetch_userprofile and weibo_user.info.is_person and not weibo_user.info.location:
            yield 'http://weibo.com/p/%s/info' %  pid_
