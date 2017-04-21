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

from utils import get_ip_proxy,parse_datetime,to_unicode
from conf import user_config,user_agent,starts
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
        #print(user_agent)
        
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
                self.logger.info("%s: blog has sync up after %s" % (self.uid,effective_start_date.strftime("%Y%m%d")))
                finished = True
                break

            if 'end_id' not in params:
                params['end_id'] = mid
            # skip
            if weibo_user.newest_mids and not mid in weibo_user.newest_mids:
                self.logger.info("%s: reach earliest blog %s" % (self.uid,mid))
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
            # has_video
            mblog.has_video = div.find('div',attrs={'node-type':'fl_h5_video_disp'}) or div.find('span',attrs={'class':'icon_playvideo'})
            mblog.save()
            self.counter.inc('processed_weibo_posts', 1)

            # fetch forwards and comments
            if self.uid in starts:
                query = {'id': mid, '_t': 0, '__rnd': int(time.time() * 1000)}
                query_str = urllib.urlencode(query)
                if fetch_forward and mblog.n_forwards > 0:
                    forward_url = 'http://weibo.com/aj/mblog/info/big?%s' % query_str
                    yield forward_url
                if fetch_comment and mblog.n_comments > 0:
                    comment_url = 'http://weibo.com/aj/comment/big?%s' % query_str
                    yield comment_url
                if fetch_like and mblog.n_likes > 0:
                    query = {'mid': mid, '_t': 0, '__rnd': int(time.time() * 1000)}
                    query_str = urllib.urlencode(query)
                    like_url = 'http://weibo.com/aj/like/big?%s' % query_str
                    yield like_url

            yield '%s?%s' % (url.split('?')[0], urllib.urlencode(params))


        if params.has_key('pagebar'):
            params['max_id'] = max_id
        elif params.has_key('max_id'):
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


class UserHomePageParser(WeiboParser):
    def parse(self, url=None):
        if self.bundle.exists is False:
            return
        url = url or self.url
        html = ''
        opener = None
        try:
            if hasattr(self.opener,'spynnerbr'):
                opener = self.opener.spynnerbr
            else:
                opener = SpynnerOpener(timeout=40)
                p_ = get_ip_proxy()
                self.logger.info(p_)
                opener.br.set_proxy(p_) 
                self.opener.spynnerbr = opener

            #opener.br.debug_level =1
            #t = QT4_Py_Cookie()
            #t.toQtCookieJar(self.opener.cj,opener.br.cookiejar)
            
            # wait_for_text = "$CONFIG['page_id']=",
            opener.spynner_open(url,tries=1,headers=[('User-Agent',user_config.conf.opener.user_agent)])
            self.logger.info(opener.br.url)
            html = to_unicode(opener.br.contents)
        except Exception, ex:
            
            self.logger.error(ex)
        #finally:
        #    if opener:
        #        opener.br.close()
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
                opener.br.close()
            if hasattr(self.opener,'spynnerbr'):
                del self.opener.spynnerbr
            print(html)

            raise Exception("get banned on user page")

        domain_ = re.findall("CONFIG\['domain'\]='(.*)';",html)[0]
        div_pi = soup.find('div',attrs={'class','PCD_person_info'})
        # verfiy cop
        bs_verify = div_pi.find('a',attrs={'class':'icon_verify_co_v'})
        weibo_user.info.is_person = False if bs_verify else True
        
        # vip person
        bs_vip = div_pi.find('a',attrs={'class':'icon_verify_v'})
        weibo_user.info.vip = True if bs_vip else False
        weibo_user.info.verified = True if bs_verify or bs_vip else False
        # nickname
        nickname_ = soup.find('div',attrs={'class','pf_username'}).text
        self.bundle.pid = pid_
        self.bundle.domain = domain_
        weibo_user.pid = pid_
        weibo_user.info.domain = domain_
        weibo_user.info.nickname = nickname_.strip()
        # msg counter
        tds = soup.find('table', attrs={'class': 'tb_counter'}).find_all('td')
        weibo_user.info.n_follows = int(tds[0].find('strong').text)
        weibo_user.info.n_fans = int(tds[1].find('strong').text)
        weibo_user.info.n_msgs = int(tds[2].find('strong').text)
        
        weibo_user.info.level = int(div_pi.find('a',attrs={'class':'W_icon_level'}).text.split('.')[1])
        
        weibo_user.save()

        # counter add one for the processed user home list url
        self.counter.inc('processed_weibo_user_home_page', 1)

        if fetch_userprofile and weibo_user.info.is_person and not weibo_user.info.location:
            yield 'http://weibo.com/p/%s/info' %  pid_

class ForwardCommentLikeParser(WeiboParser):
    strptime_lock = Lock()
    
    def _strptime(self, string, format_):
        self.strptime_lock.acquire()
        try:
            return datetime.strptime(string, format_)
        finally:
            self.strptime_lock.release()
        
    def parse_datetime(self, dt_str):
        dt = None
        if u'秒' in dt_str:
            sec = int(dt_str.split(u'秒', 1)[0].strip())
            dt = datetime.now() - timedelta(seconds=sec)
        elif u'分钟' in dt_str:
            sec = int(dt_str.split(u'分钟', 1)[0].strip()) * 60
            dt = datetime.now() - timedelta(seconds=sec)
        elif u'今天' in dt_str:
            dt_str = dt_str.replace(u'今天', datetime.now().strftime('%Y-%m-%d'))
            dt = self._strptime(dt_str, '%Y-%m-%d %H:%M')
        elif u'月' in dt_str and u'日' in dt_str:
            this_year = datetime.now().year
            date_str = '%s %s' % (this_year, dt_str)
            if isinstance(date_str, unicode):
                date_str = date_str.encode('utf-8')
            dt = self._strptime(date_str, '%Y %m月%d日 %H:%M')
        else:
            dt = parse(dt_str)
        return dt
    
    def parse(self, url=None):
        if self.bundle.exists is False:
            return
        
        url = url or self.url
        br = self.opener.browse_open(url)
        try:
            jsn = json.loads(br.response().read())
        except ValueError:
            raise FetchBannedError('fetch banned by weibo server')

#         self.logger.debug('load %s finish' % url)

        try:
            soup = beautiful_soup(jsn['data']['html'])
            current_page = jsn['data']['page']['pagenum']
            n_pages = jsn['data']['page']['totalpage']
        except KeyError:
            raise FetchBannedError('fetch banned by weibo server')
        
        if not self.check(url, br):
            return
        
        decodes = urldecode(url)
        mid = decodes.get('id', decodes.get('mid'))
        
        mblog = self.bundle.current_mblog
        if mblog is None or mblog.mid != mid:
            try:
                mblog = getattr(MicroBlog, 'objects').get(Q(mid=mid) & Q(uid=self.uid))
            except DoesNotExist:
                mblog = MicroBlog(mid=mid, uid=self.uid)
                mblog.save()
        
        def set_instance(instance, dl):
            instance.avatar = dl.find('dt').find('img')['src']
            date = dl.find('dd').find(attrs={'class': 'S_txt2'}).text
            date = date.strip().strip('(').strip(')')
            instance.created = self.parse_datetime(date)
            for div in dl.find_all('div'): div.extract()
            for span in dl.find_all('span'): span.extract()
            instance.content = dl.text.strip()

        counter_type = None
        if url.startswith('http://weibo.com/aj/comment'):
            counter_type = 'comment'
            dls = soup.find_all('dl', mid=True)
            for dl in dls:
                uid = dl.find('a', usercard=True)['usercard'].split("id=", 1)[1]
                comment = Comment(uid=uid)
                set_instance(comment, dl)
                
                mblog.comments.append(comment)
                yield WeiboUserBundle(str(uid))
        elif url.startswith('http://weibo.com/aj/mblog/info'):
            counter_type = 'forward'
            dls = soup.find_all('dl', mid=True)
            for dl in dls:
                forward_again_a = dl.find('a', attrs={'action-type': re.compile("^(feed_list|fl)_forward$")})
                uid = urldecode('?%s' % forward_again_a['action-data'])['uid']
                forward = Forward(uid=uid, mid=dl['mid'])
                set_instance(forward, dl)
                
                mblog.forwards.append(forward)
                yield WeiboUserBundle(str(uid))
        elif url.startswith('http://weibo.com/aj/like'):
            counter_type = 'like'
            lis = soup.find_all('li', uid=True)
            for li in lis:
                like = Like(uid=li['uid'])
                like.avatar = li.find('img')['src']
                
                mblog.likes.append(like)
                yield WeiboUserBundle(str(uid))
        mblog.save()

        # counter add one for the processed forward or comment or like list url
        if counter_type is not None:
            self.counter.inc('processed_%s_list_page' % counter_type, 1)

        if current_page >= n_pages:
            return
        
        params = urldecode(url)
        new_params = urldecode('?page=%s' % (current_page + 1))
        params.update(new_params)
        params['__rnd'] = int(time.time() * 1000)
        next_page = '%s?%s' % (url.split('?')[0] , urllib.urlencode(params))
        yield next_page
    
    
class UserInfoParser(WeiboParser):
    def parse(self, url=None):
        if self.bundle.exists is False:
            return
        
        url = url or self.url
        # add proxy
        p_ = get_ip_proxy()
        if p_:
            self.opener.remove_proxy()
            self.opener.add_proxy(p_)

        br = self.opener.browse_open(url)
#         self.logger.debug('load %s finish' % url)
        soup = beautiful_soup(br.response().read())
        
        if not self.check(url, br):
            return
        
        weibo_user = self.get_weibo_user()
        info = weibo_user.info
        if info is None:
            weibo_user.info = UserInfo()
            
        new_style = False
        
        profile_div = None
        career_div = None
        edu_div = None
        tags_div = None
        for script in soup.find_all('script'):
            text = script.text
            if text.startswith('FM.view'):
                text = text.strip().replace(';', '').replace('FM.view(', '')[:-1]
                data = json.loads(text)
                domid = data['domid']
                if domid.startswith('Pl_Official_LeftInfo__'):
                    info_soup = beautiful_soup(data['html'])
                    info_div = info_soup.find('div', attrs={'class': 'profile_pinfo'})
                    for block_div in info_div.find_all('div', attrs={'class': 'infoblock'}):
                        block_title = block_div.find('form').text.strip()
                        if block_title == u'基本信息':
                            profile_div = block_div
                        elif block_title == u'工作信息':
                            career_div = block_div
                        elif block_title == u'教育信息':
                            edu_div = block_div
                        elif block_title == u'标签信息':
                            tags_div = block_div
                elif domid.startswith('Pl_Official_PersonalInfo__'):
                    new_style = True
                    info_soup = beautiful_soup(data['html'])
                    for block_div in info_soup.find_all('div', attrs={'class': 'WB_cardwrap'}):
                        block_title_div = block_div.find('h4', attrs={'class': 'obj_name'})
                        if block_title_div is None:
                            block_title_div = block_div.find('div', attrs={'class': 'obj_name'})\
                                .find('h2')
                        if block_title_div is None:
                            continue
                        block_title = block_title_div.text.strip()
                        inner_div = block_div.find('div', attrs={'class': 'WB_innerwrap'})
                        if block_title == u'基本信息':
                            profile_div = inner_div
                        elif block_title == u'工作信息':
                            career_div = inner_div
                        elif block_title == u'教育信息':
                            edu_div = inner_div
                        elif block_title == u'标签信息':
                            tags_div = inner_div
                elif domid == 'Pl_Official_Header__1':
                    header_soup = beautiful_soup(data['html'])
                    weibo_user.info.avatar = header_soup.find('div', attrs={'class': 'pf_head_pic'})\
                                                .find('img')['src']
                    
                    weibo_user.info.n_follows = int(header_soup.find('ul', attrs={'class': 'user_atten'})\
                                                    .find('strong', attrs={'node-type': 'follow'}).text)
                    weibo_user.info.n_fans = int(header_soup.find('ul', attrs={'class': 'user_atten'})\
                                                 .find('strong', attrs={'node-type': 'fans'}).text)
                elif domid.startswith('Pl_Core_T8CustomTriColumn__'):
                    # new style friends info
                    header_soup = beautiful_soup(data['html'])
                    tds = header_soup.find('table', attrs={'class': 'tb_counter'})\
                                                .find_all('td')
                    weibo_user.info.n_follows = int(tds[0].find('strong').text)
                    weibo_user.info.n_fans = int(tds[1].find('strong').text)
                elif domid.startswith('Pl_Official_Headerv6__'):
                    # new style avatar info
                    header_soup = beautiful_soup(data['html'])
                    weibo_user.info.avatar = header_soup.find('p', attrs='photo_wrap')\
                                                .find('img')['src']
                    bs_verified = header_soup.find('a',attrs={"suda-data":"key=pc_apply_entry&value=feed_icon"})
                    weibo_user.info.verified = True if bs_verified else False
                    bs_vip = header_soup.find('a',attrs={"suda-uatrack":"key=home_vip&value=home_feed_vip"})
                    weibo_user.info.vip = True if bs_vip else False
                    weibo_user.info.pf_intro = header_soup.find('div', attrs={'class': 'pf_intro'}).text
                elif domid == 'CD_person_detail':
                    header_soup = beautiful_soup(data['html'])
                    weibo_user.info.level_score = int(header_soup.find('p',attrs={'class':'level_info'}).find_all('span',attrs={'class':'S_txt1'})[1].text.strip())
                                                       
            elif 'STK' in text:
                text = text.replace('STK && STK.pageletM && STK.pageletM.view(', '')[:-1]
                data = json.loads(text)
                pid = data['pid']
                if pid == 'pl_profile_infoBase':
                    profile_div = beautiful_soup(data['html'])
                elif pid == 'pl_profile_infoCareer':
                    career_div = beautiful_soup(data['html'])
                elif pid == 'pl_profile_infoEdu':
                    edu_div = beautiful_soup(data['html'])
                elif pid == 'pl_profile_infoTag':
                    tags_div = beautiful_soup(data['html'])
                elif pid == 'pl_profile_photo':
                    soup = beautiful_soup(data['html'])
                    weibo_user.info.avatar = soup.find('img')['src']
        
        profile_map = {
            u'昵称': {'field': 'nickname'},
            u'所在地': {'field': 'location'},
            u'性别': {'field': 'sex', 
                    'func': lambda s: True if s == u'男' else False},
            u'生日': {'field': 'birth'},
            u'博客': {'field': 'blog'},
            u'个性域名': {'field': 'site'},
            u'简介': {'field': 'intro'},
            u'邮箱': {'field': 'email'},
            u'QQ': {'field': 'qq'},
            u'MSN': {'field': 'msn'},
            u'注册时间':{'field':'register_date'}
        }
        if profile_div is not None:
            if not new_style:
                divs = profile_div.find_all(attrs={'class': 'pf_item'})
            else:
                divs = profile_div.find_all('li', attrs={'class': 'li_1'})
            for div in divs:
                if not new_style:
                    k = div.find(attrs={'class': 'label'}).text.strip()
                    v = div.find(attrs={'class': 'con'}).text.strip()
                else:
                    k = div.find('span', attrs={'class': 'pt_title'}).text.strip().strip(u'：')
                    d = div.find('span', attrs={'class': 'pt_detail'})
                    if d:
                        v = d.text.strip()
                    else:
                        v = div.find('a').text.strip()
                if k in profile_map:
                    if k == u'个性域名' and '|' in v:
                        v = v.split('|')[1].strip()
                    func = (lambda s: s) \
                            if 'func' not in profile_map[k] \
                            else profile_map[k]['func']
                    v = func(v)
                    setattr(weibo_user.info, profile_map[k]['field'], v)
                
        weibo_user.info.work = []
        if career_div is not None:
            if not new_style:
                for div in career_div.find_all(attrs={'class': 'con'}):
                    work_info = WorkInfo()
                    ps = div.find_all('p')
                    for p in ps:
                        a = p.find('a')
                        if a is not None:
                            work_info.name = a.text
                            text = p.text
                            if '(' in text:
                                work_info.date = text.strip().split('(')[1].strip(')')
                        else:
                            text = p.text
                            if text.startswith(u'地区：'):
                                work_info.location = text.split(u'：', 1)[1]
                            elif text.startswith(u'职位：'):
                                work_info.position = text.split(u'：', 1)[1]
                            else:
                                work_info.detail = text
                    weibo_user.info.work.append(work_info)
            else:
                li = career_div.find('li', attrs={'class': 'li_1'})
                for span in li.find_all('span', attrs={'class': 'pt_detail'}):
                    work_info = WorkInfo()
                    
                    text = span.text
                    a = span.find('a')
                    if a is not None:
                        work_info.name = a.text
                    if '(' in text:
                        work_info.date = text.strip().split('(')[1]\
                                            .replace('\r', '')\
                                            .replace('\n', '')\
                                            .replace('\t', '')\
                                            .split(')', 1)[0]

                    for l in text.split('\r\n'):
                        l = l.strip()
                        if len(l) == 0:
                            continue
                        if l.startswith(u'地区：'):
                            work_info.location = l.split(u'：', 1)[1]
                        elif l.startswith(u'职位：'):
                            work_info.position = l.split(u'：', 1)[1]
                        else:
                            work_info.detail = text.replace('\r', '')\
                                                    .replace('\n', '')\
                                                    .replace('\t', '')\
                                                    .strip()
                    
                    weibo_user.info.work.append(work_info)
            
        weibo_user.info.edu = []
        if edu_div is not None:
            if not new_style:
                for div in edu_div.find_all(attrs={'class': 'con'}):
                    edu_info = EduInfo()
                    ps = div.find_all('p')
                    for p in ps:
                        a = p.find('a')
                        text = p.text
                        if a is not None:
                            edu_info.name = a.text
                            if '(' in text:
                                edu_info.date = text.strip().split('(')[1].strip().strip(')')
                        else:
                            edu_info.detail = text
                    weibo_user.info.edu.append(edu_info)
            else:
                span = edu_div.find('li', attrs={'class': 'li_1'})\
                                .find('span', attrs={'class': 'pt_detail'})
                text = span.text
                names = []
                for a in span.find_all('a'):
                    names.append(a.text)
                
                for idx, name in enumerate(names):
                    start_pos = text.find(name) + len(name)
                    if idx < len(names) - 1:
                        end_pos = text.find(names[idx + 1], start_pos)
                    else:
                        end_pos = len(text)
                    t = text[start_pos: end_pos]
                    
                    edu_info = EduInfo()
                    edu_info.name = name
                    if '(' in text:
                        edu_info.date = t.strip().split('(')[1]\
                                            .replace('\r', '')\
                                            .replace('\n', '')\
                                            .replace('\t', '')\
                                            .split(')', 1)[0]
                        t = t[t.find(')') + 1:]
                    text = text[end_pos:]
                    edu_info.detail = t.replace('\r', '').replace('\n', '')\
                                        .replace('\t', '').strip()
                    weibo_user.info.edu.append(edu_info)
                    
        weibo_user.info.tags = []
        if tags_div is not None:
            if not new_style:
                for div in tags_div.find_all(attrs={'class': 'con'}):
                    for a in div.find_all('a'):
                        weibo_user.info.tags.append(a.text)
            else:
                for a in tags_div.find('span', attrs={'class': 'pt_detail'}).find_all('a'):
                    weibo_user.info.tags.append(a.text.strip())

        weibo_user.save()
#         self.logger.debug('parse %s finish' % url)

        # counter add one for the profile url
        self.counter.inc('processed_profile_page', 1)
   