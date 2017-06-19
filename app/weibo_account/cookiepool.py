# coding: utf-8

import os
import threading
import random
from datetime import date
from cola.core.logs import get_logger

import shutil
import argparse
from login import WeiboLogin

from cola.core.opener import MechanizeOpener
from cola.utilities.util_fetch import get_ip_proxy

"""
    generate cookie db and provide access
"""
base_dir = os.path.dirname(os.path.abspath(__file__))
cookie_dir = os.path.join(base_dir,"cookies")

class CookieManager:
    """
        a clsss that manage weibo cookie
    """
    def __init__(self):
        self.count = -1
        self.logger = get_logger("cookie_pool")
        self.validated = []

    def refresh_cookies(self, ck_dir):
        """
            refresh cookie db
        """
        idx = 0
        # del all cookies
        if os.path.isdir(cookie_dir):
            shutil.rmtree(cookie_dir)
        os.mkdir(cookie_dir)
        # add cookie from folder
        accounts = []
        for root,dirs,files in os.walk(ck_dir):           
            for filespath in files:
                full_name = os.path.join(root,filespath)
                with open(full_name) as f:
                    for line in f.readlines():
                        if line:
                            u,p = line.split('\t')
                            if u and p:
                                accounts.append((u.strip(),p.strip()))
        # save cookie
        for u,p in accounts:
            opener = MechanizeOpener(user_agent='Baiduspider+(+http://www.baidu.com/search/spider.htm)',timeout=10)
            opener.browser.set_proxies({'http': get_ip_proxy(size=10)})
            lm = WeiboLogin(opener,u,p)
            try:
                status = lm.login()
            except Exception as ex:
                self.logger.warn("login error:%s" % u)
                self.logger.error(ex)
                continue
            if status:
                idx +=1
                opener.cj.save(os.path.join(cookie_dir , '%d.txt' % idx),ignore_discard=True,ignore_expires=True)
                self.validated.append("%s\t%s\r\n" % (u,p))
            opener.close()

    def get_cookiefile(self):
        rnd = random.choice(range(self.get_count()))            
        return os.path.join(cookie_dir,"cookies",'%d.txt' % rnd)

    def get_count(self):
        if self.count < 0:
            cnt = 0
            for root,dirs,files in os.walk(os.path.join(base_dir,'cookies')):
                for filespath in files:
                    if filespath.endswith('.txt'):
                        cnt +=1
            self.count = cnt
        return self.count

    def dump_validated(self):
        with open(os.path.join(base_dir,"account.txt"),'w') as f:
            f.writelines(self.validated)
            f.close()
        
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test and Dump weibo cookies')
    parser.add_argument('-f','--file', help='weibo account dir')
    args = parser.parse_args()
    if args.file:
        cm = CookieManager()
        cm.refresh_cookies(args.file)
        cm.dump_validated()

