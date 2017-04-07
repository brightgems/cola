from cookielib import Cookie, LWPCookieJar, CookieJar
from PyQt4.QtCore import QDateTime
from PyQt4.QtNetwork import QNetworkCookie, QNetworkCookieJar

class QT4_Py_Cookie(object):
    @staticmethod
    def toQtCookie(PyCookie):
        qc = QNetworkCookie(PyCookie.name, PyCookie.value)
        qc.setSecure(PyCookie.secure)
        if PyCookie.path_specified:
            qc.setPath(PyCookie.path)
        if PyCookie.domain != "":
            qc.setDomain(PyCookie.domain)
        if PyCookie.expires and PyCookie.expires != 0:
            t = QDateTime()
            t.setTime_t(PyCookie.expires)
            qc.setExpirationDate(t)
        # not yet handled(maybe less useful):
        # py cookie.rest / QNetworkCookie.setHttpOnly()
        return qc

    @staticmethod
    def toPyCookie(QtCookie):
        port = None
        port_specified = False
        secure = QtCookie.isSecure()
        name = QtCookie.name().data().decode()
        value = QtCookie.value().data().decode()
        v = unicode(QtCookie.path())
        path_specified = bool(v != "")
        path = v if path_specified else None
        v = unicode(QtCookie.domain())
        domain_specified = bool(v != "")
        domain = v
        if domain_specified:
            domain_initial_dot = v.startswith('.')
        else:
            domain_initial_dot = None
        v = int(QtCookie.expirationDate().toTime_t())
        expires = 2147483647 if v > 2147483647 else v
        rest = {"HttpOnly": QtCookie.isHttpOnly()}
        discard = False
        return Cookie(
            0,
            name,
            value,
            port,
            port_specified,
            domain,
            domain_specified,
            domain_initial_dot,
            path,
            path_specified,
            secure,
            expires,
            discard,
            None,
            None,
            rest,
        )

    def toPyCookieJar(self, QtCookieJar, PyCookieJar):
        for c in QtCookieJar.allCookies():
            PyCookieJar.set_cookie(self.toPyCookie(c))

    def toQtCookieJar(self, PyCookieJar, QtCookieJar, keep_old=False):
        allCookies = QtCookieJar.allCookies() if keep_old else []
        for pc in PyCookieJar:
            qc = self.toQtCookie(pc)
            allCookies.append(qc)
        QtCookieJar.setAllCookies(allCookies)

    def load_cookies(self, cookie_storage, keep_old=False):
        """load from cookielib's CookieJar or Set-Cookie3 format text file.

        :param cookie_storage: file location string on disk or CookieJar
            instance.
        :param keep_old: Don't reset, keep cookies not overridden.
        """
        cookie_jar = QNetworkCookieJar()
        if cookie_storage.__class__.__name__ == 'str':
            cj = LWPCookieJar(cookie_storage)
            cj.load()
            self.toQtCookieJar(cj, cookie_jar)
        elif cookie_storage.__class__.__name__.endswith('CookieJar'):
            self.toQtCookieJar(cookie_storage, cookie_jar, keep_old)
        else:
            raise ValueError('unsupported cookie_storage type.')
        return cookie_jar

    def save_cookies(self, cookie_storage, cookie_jar):
        """Save to http.cookiejar's CookieJar or Set-Cookie3 format text file.

        :param cookie_storage: file location string or CookieJar instance.
        :param cookie_jar: http.cookiejar's Cookiejar for save.
        """
        if cookie_storage.__class__.__name__ == 'str':
            cj = LWPCookieJar(cookie_storage)
            self.toPyCookieJar(cookie_jar, cj)
            cj.save()
        elif cookie_storage.__class__.__name__.endswith('CookieJar'):
            self.toPyCookieJar(cookie_jar, cookie_storage)
        else:
            raise ValueError('unsupported cookie_storage type.')