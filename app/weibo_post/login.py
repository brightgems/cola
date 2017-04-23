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
import random
# app modules
from cola.core.logs import get_logger
from cola.core.errors import DependencyNotInstalledError,\
                             LoginFailure
from cola.utilities.yundama import YunDaMa

try:
    import rsa
except ImportError:
    raise DependencyNotInstalledError("rsa")

class WeiboLoginFailure(LoginFailure): pass

class WeiboLogin(object):
    def __init__(self, opener, username, passwd):
        self.opener = opener
        self.logger = get_logger("weibo.login")
        self.username = username
        self.passwd = passwd
        self.weibo_url = 'http://weibo.com/'
        self.prelogin_url = 'https://login.sina.com.cn/sso/prelogin.php'
        self.login_url = 'http://login.sina.com.cn/sso/login.php?client=ssologin.js(v1.4.18)'
        self.captcha_url ='http://login.sina.com.cn/cgi/pin.php'
        
    def get_user(self, username):
        username = urllib.quote(username)
        return base64.encodestring(username)[:-1]
    
    def get_passwd(self, passwd, pubkey, servertime, nonce):
        key = rsa.PublicKey(int(pubkey, 16), int('10001', 16))
        message = str(servertime) + '\t' + str(nonce) + '\n' + str(passwd)
        passwd = rsa.encrypt(message, key)
        return binascii.b2a_hex(passwd)
    
    def getPin(self,pcid):
        '''
        验证码
        '''
        para = {
            'p': pcid,
            'r': random.randint(10000,100000),
            's': 0
        }

        import urllib
        url = '%s?%s' % (self.captcha_url, urllib.urlencode(para))

        pic = self.opener.open(url)
        file('pin.png','wb').write(pic)
        return pic

    def get_verify_cd(self,pic):
        ydm = YunDaMa("brtgpy", "8ik,*IK<")
        cid_t, code_t = ydm.get_captcha("captcha.jpeg", pic)
        print(cid_t, code_t)
        if cid_t and (not code_t):
            return ydm.result(cid_t)
        return code_t

    def prelogin(self):
        username = self.get_user(self.username)
        prelogin_url = 'http://login.sina.com.cn/sso/prelogin.php?entry=sso&callback=sinaSSOController.preloginCallBack&su=%s&rsakt=mod&checkpin=1&client=ssologin.js(v1.4.18)' % username
        data = self.opener.open(prelogin_url)
        regex = re.compile('\((.*)\)')
        try:
            json_data = regex.search(data).group(1)
            data = json.loads(json_data)
            
            return str(data['servertime']), data['nonce'], \
                data['pubkey'], data['rsakv'],data.get('showpin', 0),data.get('pcid', '')

            
        except:
            raise WeiboLoginFailure
        
    def login(self):
        login_url = 'http://login.sina.com.cn/sso/login.php?client=ssologin.js(v1.4.18)'
        
        try:
            servertime, nonce, pubkey, rsakv,showpin,pcid = self.prelogin()
            postdata = {
                'entry': 'weibo',
                'gateway': '1',
                'from': '',
                'savestate': '7',
                'userticket': '1',
                'pagerefer': 'http://login.sina.com.cn/sso/logout.php',
                'vsnf': '1',
                'su': self.get_user(self.username),
                'service': 'weibo',
                'servertime': servertime,
                'nonce': nonce,
                'pwencode': 'rsa2',
                'rsakv' : rsakv,				
                'sp': self.get_passwd(self.passwd, pubkey, servertime, nonce),
                'sr': '1920*1080',				
                'encoding': 'UTF-8',
                'prelt': '115',
                'cdult':3,
                'returntype': 'TEXT'
            }

            if showpin == 1:
                pic = self.getPin(pcid)
                vcode = self.get_verify_cd(pic)
                if vcode:
                    postdata['door'] = vcode
                    postdata['cdult'] = 2
                    postdata['pcid'] = pcid
                    postdata['prelt'] = 2041
                else:
                    self.logger.warn("failed yudama")
            
            postdata = urllib.urlencode(postdata)
            text = self.opener.open(login_url, postdata)

            # Fix for new login changed since about 2014-3-28
            
            if "retcode" in text:
                json_data = json.loads(text)
                if 'reason' in json_data:
                    return False, json_data['reason']
                else:
                    ajax_url = json_data['crossDomainUrlList'][0]
                    text = self.opener.open(ajax_url)
            else:
                return False        
            self.logger.info("weibo login successfuly as `%s`" % self.username)
            return(True)			
        except WeiboLoginFailure:
            return False
