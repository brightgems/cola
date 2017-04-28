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
import json
import urlparse
import urllib
from urllib2 import URLError
from six.moves import urllib_parse
from datetime import datetime, timedelta
import time
import re

try:
    from dateutil.parser import parse
except ImportError:
    raise DependencyNotInstalledError('python-dateutil')

from cola.core.parsers import Parser
from cola.core.errors import DependencyNotInstalledError, FetchBannedError
from cola.core.utils import urldecode, beautiful_soup
from cola.utilities.util_parse import to_unicode
from cola.utilities.util_fetch import get_ip_proxy
from cola.core.unit import Url

from conf import user_config, starts, effective_start_date, fetch_userprofile, fetch_related_keywords
from bundle import WeiboSearchBundle
from storage import DoesNotExist, Q, WeiboUser,\
                    MicroBlog, Geo, UserInfo, WorkInfo, EduInfo,\
                    Comment, Forward, Like

class WeiboParser(Parser):
    def __init__(self, opener = None, url = None, bundle = None, **kwargs):
        super(WeiboParser, self).__init__(opener=opener, url=url, **kwargs)
        
        if not hasattr(self, 'logger') or self.logger is None:
            self.logger = get_logger(name='weibo_parser')
        self.uid = None
    
    def _check_url(self, dest_url, src_url):
        return dest_url.split('?')[0] == src_url.split('?')[0]
    
    def check(self, url, br):
        dest_url = br.geturl()
        if not self._check_url(dest_url, url):
            if dest_url.startswith('http://weibo.com/login.php'):
                raise WeiboLoginFailure('Weibo not login or login expired')
            if dest_url.startswith('http://weibo.com/sorry?usernotexists'):
                return False
        return True

    def get_weibo_user(self,uid):
        
        try:
            weibo_user = getattr(WeiboUser, 'objects').get(uid=uid)
        except DoesNotExist:
            weibo_user = WeiboUser(uid=uid)
        return weibo_user

class WeiboSearchParser(WeiboParser):
    def __init__(self, opener = None, url = None, bundle = None, **kwargs):
        super(WeiboSearchParser, self).__init__(opener=opener, url=url, **kwargs)
        
    def get_microblog(self, mid, keyword):
        try:
            weibo = getattr(MicroBlog, 'objects').get(Q(mid=mid) & Q(keyword=keyword))
            return weibo, True
        except DoesNotExist:
            weibo = MicroBlog(mid=mid, keyword=keyword)
            weibo.save()
            return weibo, False

    def save_blog_detail(self,div,mblog):
        
        content_div = div.find('p', attrs={'node-type': 'feed_list_content'})
        mblog.content = content_div.text
        blog_create_date = parse(div.find('a',attrs={'node-type':'feed_list_item_date'})['title'])
        mblog.created = blog_create_date
        mblog.last_update = datetime.now()

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
        

        func_div = div.find_all('div', attrs={'class':'feed_action'})[-1]
        action_type_re = lambda t: re.compile("^(feed_list|fl)_%s$" % t)
            
        likes = func_div.find('a', attrs={'action-type': action_type_re("like")}).find('em')
        if likes:
            likes = likes.text.strip('(').strip(')').replace(',','')
            likes = int(likes) if likes and unicode.isdigit(likes) else 0
            mblog.n_likes = likes
        forwards = func_div.find('a', attrs={'action-type': action_type_re("forward")}).find('em')
        if forwards:
            forwards = forwards.text.strip('(').strip(')').replace(',','')
            mblog.n_forwards = int(forwards) if forwards and unicode.isdigit(forwards) else 0
        comments = func_div.find('a', attrs={'action-type': action_type_re('comment')}).find('em')
        if comments:
            comments = comments.text.strip('(').strip(')').replace(',','')
            mblog.n_comments = int(comments) if comments and unicode.isdigit(comments) else 0
        # parse uid
        a = func_div.find('a',attrs={'action-type':'feed_list_forward'})['action-data']
        u = urllib_parse.unquote(a[a.find('url='):])
        qs = urllib_parse.parse_qs(u)
        if not qs.has_key('uid'):
            print(qs)
        mblog.uid = qs['uid'][0]

        # save user
        weibo_user = self.get_weibo_user(mblog.uid)
        if not (weibo_user.info and weibo_user.info.nickname):
            if qs.has_key('pid'):
                weibo_user.pid = qs['pid'][0]
            if weibo_user.info is None:
                weibo_user.info = UserInfo()
                weibo_user.info.nickname = qs['name'][0]
            weibo_user.save()
    
        # has_video
        div_video = div.find('div',attrs={'node-type':'fl_h5_video_disp'}) or div.find('span',attrs={'class':'icon_playvideo'})
        mblog.has_video = True if div_video else False
        mblog.save()
        return (weibo_user,mblog)
        
    def parse(self, url = None):
        url = url or self.url
        
        html = to_unicode(self.opener.open(url,timeout=10))

        if not 'pl_weibo_direct' in html:
            raise FetchBannedError()
        # find page_id
        try:
            keyword = re.findall("CONFIG\['s_search'\]\s+=\s+'(.*)'",html)[0]
        except:
            raise FetchBannedError("get banned on user page")
        

        soup = beautiful_soup(html)

        for script in soup.find_all('script'):
            text = script.text
            if text.startswith('STK && STK.pageletM && STK.pageletM.view'):
                text = text.strip().replace(';', '').replace('STK && STK.pageletM && STK.pageletM.view(', '')[:-1]
                data = json.loads(text)
                pid = data['pid']
                if pid == "pl_weibo_direct":
                    #region extract_mblogs
                    header_soup = beautiful_soup(data['html'])
                    finished = False
                    feed_list_items = header_soup.find_all('div', attrs={'action-type': 'feed_list_item'}, mid=True)
                    for dl in feed_list_items:
                        mid = dl['mid']
                        self.logger.debug('mid:%s' % mid)
                        mblog, finished = self.get_microblog(mid, keyword)
                        weibo_user,mblog = self.save_blog_detail(dl,mblog)

                        if fetch_userprofile and not weibo_user.info.gender:
                            uid = weibo_user.uid
                            start = int(time.time() * (10 ** 6))
                            yield 'http://weibo.com/%s?is_all=1&_rnd=%s' % (uid, start)
                        # skip all following blogs if create date less than
                        # effective start date
                        blog_create_date = mblog.created
                        if (blog_create_date - effective_start_date).days < 0:
                            self.logger.info("%s: blog has sync up after %s" % (uid,effective_start_date.strftime("%Y%m%d")))
                            finished = True
                            break
                        #if finished:
                        #    self.logger.info('reach post processed last time,
                        #    quit task!')
                        #    break
                    #endregion
                    if not finished:
                        pages = header_soup.find('div', attrs={'class': 'W_pages'})
                        if pages is None or len(list(pages.find_all('a'))) == 0:
                            finished = True
                        else:
                            next_page = pages.find_all('a')[-1]
                            if next_page.text.strip() == u'下一页':
                                next_href = next_page['href']
                                if not next_href.startswith('http://'):
                                    next_href = urlparse.urljoin('http://s.weibo.com', next_href)
                                yield next_href
                            else:
                                finished = True
                    #else:
                    #    bundle = Url(keyword, force=True)
                    # return [], [bundle]
                elif pid == "pl_weibo_relation":
                    # only grab related keyword at 1st level
                    if fetch_related_keywords and keyword in starts:
                        header_soup = beautiful_soup(data['html'])
                        rws = header_soup.find_all('a',attrs={'suda-data':'key=tblog_search_weibo&value=weibo_relate'})
                        for w in rws:
                            next_href = w['href']
                            next_href = urlparse.urljoin('http://s.weibo.com', next_href)
                            yield next_href
        yield [], []

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


    def parse(self, url = None):
        url = url or self.url
        html = ''
        opener = self.opener
        
        try:
            
            opener.addheaders = [('User-Agent',user_config.conf.opener.user_agent)]
            html = to_unicode(opener.open(url,timeout=10))
            
            opener.browser.clear_history() # resolve memory issue
        except Exception, ex:
            
            if opener:
                opener.browser.close()
            raise Exception("get banned on user page")
        
        try:
            uid = re.findall("CONFIG\['oid'\]='(.*)';",html)[0]
        except:
            raise FetchBannedError("get banned on blog page")

        soup = beautiful_soup(html)
        weibo_user = self.get_weibo_user(uid)
        if weibo_user.info is None:
            weibo_user.info = UserInfo()

        # find page_id
        try:
            pid_ = re.findall("CONFIG\['page_id'\]='(.*)';",html)[0]
        except:
            raise FetchBannedError("get banned on user page")

        domain_ = re.findall("CONFIG\['domain'\]='(.*)';",html)[0]

        for script in soup.find_all('script'):
            text = script.text
            if text.startswith('FM.view'):
                text = text.strip().replace(';', '').replace('FM.view(', '')[:-1]
                data = json.loads(text)
                domid = data['domid']
                if domid.startswith("Pl_Core_UserInfo") and data.has_key('html'):
                    header_soup = beautiful_soup(data['html'])
                    self.extract_user_info(header_soup,weibo_user)
                elif domid.startswith("Pl_Official_Header"):  
                    header_soup = beautiful_soup(data['html'])
                    # nickname
                    nickname_ = header_soup.find('div',attrs={'class','pf_username'}).text
                elif domid.startswith("Pl_Core_T8CustomTriColumn") and data.has_key('html'):  
                    header_soup = beautiful_soup(data['html'])
                    self.extract_user_counter(header_soup,weibo_user)

        weibo_user.pid = pid_
        weibo_user.info.domain = domain_
        weibo_user.info.nickname = nickname_.strip()
        weibo_user.save()

        # counter add one for the processed user home list url
        self.counter.inc('processed_weibo_user_home_page', 1)
