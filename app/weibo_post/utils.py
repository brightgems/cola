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

Created on 2013-7-6

@author: Chine
'''
import requests
import json
import random

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

def parse_datetime(dt_str):
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
        dt = self._strptime(date_str, u'%Y %m月%d日 %H:%M')
    else:
        dt = parse(dt_str)
    return dt

def base62_encode(num, alphabet=ALPHABET):
    """Encode a number in Base X

    `num`: The number to encode
    `alphabet`: The alphabet to use for encoding
    """
    if (num == 0):
        return alphabet[0]
    arr = []
    base = len(alphabet)
    while num:
        rem = num % base
        num = num // base
        arr.append(alphabet[rem])
    arr.reverse()
    return ''.join(arr)

def base62_decode(string, alphabet=ALPHABET):
    """Decode a Base X encoded string into the number

    Arguments:
    - `string`: The encoded string
    - `alphabet`: The alphabet to use for encoding
    """
    base = len(alphabet)
    strlen = len(string)
    num = 0

    idx = 0
    for char in string:
        power = (strlen - (idx + 1))
        num += alphabet.index(char) * (base ** power)
        idx += 1

    return num

def url_to_mid(url):
    '''
    >>> url_to_mid('z0JH2lOMb')
    3501756485200075L
    >>> url_to_mid('z0Ijpwgk7')
    3501703397689247L
    >>> url_to_mid('z0IgABdSn')
    3501701648871479L
    >>> url_to_mid('z08AUBmUe')
    3500330408906190L
    >>> url_to_mid('z06qL6b28')
    3500247231472384L
    >>> url_to_mid('yCtxn8IXR')
    3491700092079471L
    >>> url_to_mid('yAt1n2xRa')
    3486913690606804L
    '''
    url = str(url)[::-1]
    size = len(url) / 4 if len(url) % 4 == 0 else len(url) / 4 + 1
    result = []
    for i in range(size):
        s = url[i * 4: (i + 1) * 4][::-1]
        s = str(base62_decode(str(s)))
        s_len = len(s)
        if i < size - 1 and s_len < 7:
            s = (7 - s_len) * '0' + s
        result.append(s)
    result.reverse()
    return int(''.join(result))

def mid_to_url(midint):
    '''
    >>> mid_to_url(3501756485200075)
    'z0JH2lOMb'
    >>> mid_to_url(3501703397689247)
    'z0Ijpwgk7'
    >>> mid_to_url(3501701648871479)
    'z0IgABdSn'
    >>> mid_to_url(3500330408906190)
    'z08AUBmUe'
    >>> mid_to_url(3500247231472384)
    'z06qL6b28'
    >>> mid_to_url(3491700092079471)
    'yCtxn8IXR'
    >>> mid_to_url(3486913690606804)
    'yAt1n2xRa'
    '''
    midint = str(midint)[::-1]
    size = len(midint) / 7 if len(midint) % 7 == 0 else len(midint) / 7 + 1
    result = []
    for i in range(size):
        s = midint[i * 7: (i + 1) * 7][::-1]
        s = base62_encode(int(s))
        # New fixed
        s_len = len(s)
        if i < size - 1 and len(s) < 4:
            s = '0' * (4 - s_len) + s
        # Fix end
        result.append(s)
    result.reverse()
    return ''.join(result)

def get_avatar_size_url(img_url, size=50):
    assert size == 50 or size == 180
    splits = img_url.split('/')
    current_size = int(splits[-3])
    if current_size == size:
        return img_url
    splits[-3] = str(size)
    return '/'.join(splits)


lshttp_ = None
def get_ip_proxy():
    '''
    >>> get_ip_proxy()
    
    '''
    global lshttp_
    if not lshttp_:
        myipproxy_url = "http://ipmomentum.online/api/proxy/fast"
        rsp = requests.get(myipproxy_url,auth=('eyJhbGciOiJIUzI1NiJ9.eyJpZCI6MX0._6jmLfy5i96Ux_fLqIXwTHySY8rdSjvHGJw5VedbZ1I','unset'))
        proxys = json.loads(rsp.text)
        lshttp_ =  [p_ for p_ in proxys if p_['type']!='https']
    
    p_=random.choice(lshttp_)
    return p_['addr']
    
if __name__ == "__main__":
    #import doctest
    #doctest.testmod()
    print(get_ip_proxy())