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

import re
from datetime import datetime


from cola.core.parsers import Parser
from cola.core.utils import beautiful_soup
from cola.core.errors import DependencyNotInstalledError, FetchBannedError
from cola.core.logs import get_logger
from cola.core.opener import MechanizeOpener
from cola.core.errors import DependencyNotInstalledError,\
                             LoginFailure
from urllib2 import URLError

from storage import DoesNotExist, DoubanMovie
import urlparse


TIMEOUT = 30.0

class DoubanLoginFailure(LoginFailure): pass

class DoubanMovieParser(Parser):
    def __init__(self, opener=None, url=None, bundle=None, **kwargs):
        super(DoubanMovieParser, self).__init__(opener=opener, url=url, **kwargs)
        if self.opener is None:
            self.opener = MechanizeOpener()

        self.url = url
        
        self.opener.set_default_timeout(TIMEOUT)
        
        if not hasattr(self, 'logger') or self.logger is None:
            self.logger = get_logger(name='douban_parser')
    
    def get_subject_id(self,url):
        """
            extract subject id from url
        """
        id_arr = re.findall('https://movie.douban.com/subject/(\d+)',url)
        if id_arr:
            return id_arr[0]
    
    def _check_url(self, dest_url, src_url):
        """
            check whether url are same domain path
        """
        return dest_url.split('?')[0] == src_url.split('?')[0]
    
    def check(self, url, br):
        dest_url = br.geturl()
        if not self._check_url(dest_url, url):
            if dest_url.startswith('http://douban.com/login.php'):
                raise DoubanLoginFailure('Douban not login or login expired')
        return True
    
    

    def get_movie_subject(self,sid):
        try:
            movie = getattr(DoubanMovie, 'objects').get(sid=sid)
        except DoesNotExist:
            movie = DoubanMovie(sid=sid)
            movie.save()
        return movie


    def parse(self, url=None):
                
        url = url or self.url
        sid = self.get_subject_id(url)

        try:        
            br = self.opener.browse_open(url)
        except URLError:
            raise FetchBannedError()

        if not self.check(url, br):
            return
        html = br.response().read()

        if html == None:
            raise FetchBannedError()

        movie = self.get_movie_subject(sid)
        
        
        soup = beautiful_soup(html)

        if re.compile('<span class="pl">集数:</span>').findall(html):
            subtype = 't'
        else:
            subtype = 'm'

        title = soup.select("span[property='v:itemreviewed']")[0].text
        year = soup.select("div#content > h1")[0].find_all("span")[1].text[1:-1]
        # self.logger.debug(title)

        summary_tags = soup.select("span[property='v:summary']")
        if summary_tags:
            summary = summary_tags[0].text
        # tags
        tag_tags = soup.select('div .tags-body a')
        tags = [t.text for t in tag_tags]
        
        # get directors
        director_tags = soup.select('div #info > span a[rel="v:directedBy"]')
        p1 = re.compile(r'<[^>]+>(?P<director>[^<]+)</a>')
        directors = [p1.match(str(t)).group('director') for t in director_tags]

        # get stars
        star_tags = soup.select('div #info > span a[rel="v:starring"]')
        p2 = re.compile(r'<[^>]+>(?P<star>[^<]+)</a>')
        casts = [p2.match(str(t)).group('star') for t in star_tags]

        # get writers
        writers_tags = soup.select('div #info > span')[1].select('a')
        p2 = re.compile(r'<[^>]+>(?P<writer>[^<]+)</a>')
        writers = [p2.match(str(t)).group('writer') for t in writers_tags]

        # get genre
        genre_tags = soup.select('div #info > span[property="v:genre"]')
        p3 = re.compile(r'<span property="v:genre">(?P<genre>[^<]+)</span>')
        genres = [p3.match(str(t)).group('genre') for t in genre_tags]

        # get release date
        pubdate_tag = soup.select('div #info > span[property="v:initialReleaseDate"]')
        f4 = 0
        if pubdate_tag:
            p41 = re.compile(r'<[^>]+>(?P<pubdate>[^(]+)[(]中国大陆([ ]3D)*[)]<[^>]+>')
            p42 = re.compile(r'<[^>]+>(?P<pubdate>[^(]+)[(]中国内地([ ]3D)*[)]<[^>]+>')
            p43 = re.compile(r'<[^>]+>(?P<pubdate>[^(]+)[(]香港([ ]3D)*[)]<[^>]+>')
            p44 = re.compile(r'[0-9-]+')
            for t in pubdate_tag:
                m = p41.search(str(t))
                if m != None:
                    f4 = 1
                    pubdate = m.group('pubdate')
                    break
                m = p42.search(str(t))
                if m != None:
                    f4 = 1
                    pubdate = m.group('pubdate')
                    break
                m = p43.search(str(t))
                if m != None:
                    f4 = 1
                    pubdate = m.group('pubdate')
                    break
                m = p44.search(str(t))
                if m != None:
                    f4 = 1
                    pubdate = m.group()
                    break
        if f4 == 0:
            self.logger.critical('{0} has no pubdate'.format(sid))
            pubdate = year
        # append month/date if just year is known
        if len(pubdate)==4:
            pubdate = pubdate + "-12-30"
        elif len(pubdate)==7:
            pubdate = pubdate + "-30"
        pubdate = datetime.strptime(pubdate, '%Y-%m-%d')

        # get wishes
        wishes_tags = soup.select('div #subject-others-interests > .subject-others-interests-ft > a')
        #print wishes_tags
        if len(wishes_tags) == 0:
            self.logger.critical('{0} donnot have wish count'.format(sid))
        wish_count = None
        collect_count = None
        for i in range(len(wishes_tags)):
            m = re.match(u'(?P<wishes>[0-9]+)人想看',wishes_tags[i].text)
            if m:
                wish_count = m.group('wishes')
                continue

            m = re.match(u'(?P<collections>[0-9]+)人看过',wishes_tags[1].text)
            if m:
                collect_count = m.group('collections')
            
        rating_num = soup.select(r'strong.rating_num')[0].text
        rating_lvls = soup.select(r'div.ratings-on-weight span.rating_per')
        
        rating_lvls = [float(r.text[:-1])  for r in rating_lvls]
        
        # season
        season_tags = soup.select('div #info select#season]')
        if season_tags:
            episodes_count = season_tags.count  
            current_season = season_tags[0].select('option[selected]')[0].text     
        photo_url = soup.select('a[class="nbgnbg"] img')[0].attrs['src']
        #region save movie
        info_map = {
            u'制片国家/地区': {'field': 'countries'},
            u'语言': {'field': 'languages'},
            u'集数': {'field': 'episodes_count'},
            u'单集片长': {'field': 'duration'},
            u'片长': {'field': 'duration'},
            u'又名': {'field': 'aka','func': lambda v: v.split('/')},
            u'IMDb链接':{'field':'imdb_id'}
        }

        info_str = soup.select('div #info')[0].text
        for k,f in info_map.items():
            v = re.findall(k + "\:(.*)",info_str,re.MULTILINE)
            if v:
                func = (lambda s: s.strip()) \
                            if 'func' not in f \
                            else f['func']
                f_val = func(v[0])
                setattr(movie, f['field'], f_val)
        movie.sid = sid
        movie.title = title
        movie.photo_alt = photo_url
        movie.year = year
        movie.summary = summary
        movie.tags = tags
        movie.subtype = subtype
        movie.directors = directors
        movie.casts = casts
        movie.writers = writers
        movie.rating = float(rating_num)
        movie.high_rating_pct = rating_lvls[0] + rating_lvls[1]
        movie.low_rating_pct = rating_lvls[3] + rating_lvls[4]
        if wish_count:
            movie.wish_count = wish_count
        if collect_count:
            movie.collect_count = collect_count
        movie.pubdate = pubdate
        movie.genres = genres
        movie.alt = url
        movie.last_update = datetime.now()
        movie.save()

        def _is_same(out_url,url):
            return out_url.rsplit('#', 1)[0] == url

        next_urls = soup.select("div.recommendations-bd a")
        for link in next_urls:
            out_url = link.attrs['href']
            
            if not _is_same(out_url,url) and out_url.startswith("https://movie.douban.com/subject"):
                sid_next = self.get_subject_id(out_url)
                if sid_next != sid:
                    print(out_url)
                    yield out_url
        #endregion