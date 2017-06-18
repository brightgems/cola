# _*_ coding: utf-8 _*_

"""
util_fetch.py by xianhu
"""

import random
from httplib import HTTPException
import requests
import json
from .util_config import CONFIG_USERAGENT_PC, CONFIG_USERAGENT_PHONE, CONFIG_USERAGENT_ALL


__all__ = ["make_random_useragent",]


lshttp_ = None
def get_ip_proxy(size=50, https=False):
    '''
    >>> get_ip_proxy()
    
    '''
    global lshttp_
    if not lshttp_:
        fast_ipproxy_url = "http://ipmomentum.online/api/proxy/fast"
        china_ipproxy_url = "http://ipmomentum.online/api/proxy/china"
        auth_ = ('eyJhbGciOiJIUzI1NiJ9.eyJpZCI6MX0._6jmLfy5i96Ux_fLqIXwTHySY8rdSjvHGJw5VedbZ1I','unset')

        iptype = 'https' if https else 'http'
        try:
            rsp = requests.get(fast_ipproxy_url,auth=auth_)
            proxys = json.loads(rsp.text)
            lshttp_ = [p_ for p_ in proxys if p_['type'] == iptype or p_['type'] == 'all']
            # get china vip as replacement if vip count is less than 50
            if len(lshttp_) < size:
                rsp = requests.get(china_ipproxy_url,auth=auth_)
                proxys = json.loads(rsp.text)
                lshttp_.extend([p_ for p_ in proxys if p_['type'] == iptype or p_['type'] == 'all'])
        except HTTPException, ex:
            return
    
    p_ = random.choice(lshttp_[:size])
    return p_['addr']

def make_random_useragent(ua_type="pc"):
    """
    make a random user_agent based on ua_type, ua_type can be "pc", "phone" or "all"(default)
    """
    ua_type = ua_type.lower()
    assert ua_type in ("pc", "phone", "all"), "make_random_useragent: parameter ua_type[%s] is invalid" % ua_type
    return random.choice(CONFIG_USERAGENT_PC if ua_type == "pc" else (CONFIG_USERAGENT_PHONE if ua_type == "phone" else CONFIG_USERAGENT_ALL))
