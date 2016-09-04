import re, requests, imaplib, itertools
import utils
from bs4 import BeautifulSoup as BS
PARSER = 'html.parser'

class AuthenticationError(Exception):
    '''Wrong credentials submitted''' 

class WebSession(object):
    '''Generic class of a web session'''
    def initialize(self, url_login, url_auth, params=dict()):
        '''Session initialization'''
        self.session = requests.session()
        web_html = self.session.get(url_login)
        soup = BS(web_html.content, PARSER).find('form').find_all('input')
        cred = {x['name'] : x['value'] for x in soup if x.has_attr('value')}
        cred.update(params)
        self.session.post(url_auth, data=cred)

    def access(self, url, params=dict()):
        '''Get URL in current session'''
        g = self.session.get(url, params=params)
        if g.status_code == 200:
            return g.text
        return None

class GoogleSession(WebSession):
    '''Session for Google'''

    GMAIL = 'https://mail.google.com'
    METHODS = ['addresses']

    def __init__(self, login, passwd):
        self.login  = login
        cred = {'Email':login, 'Passwd':passwd}
        self.initialize(url_login='https://accounts.google.com/ServiceLogin', url_auth='https://accounts.google.com/ServiceLoginAuth', params=cred)
        if login not in self.access(self.GMAIL):
            raise AuthenticationError

    def addresses(self, passwd):
        '''Return the set of addresses in the session's inbox. Require access to less secure apps.'''
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        try:
            mail.login(self.login, passwd)
        except IMAP4.error:
            raise AuthenticationError
        mail.select("INBOX")
        _, data = mail.search(None, "ALL")
        ids = b','.login(data[0].split())
        msgs = mail.fetch(ids, '(BODY.PEEK[HEADER])')[1][0::2]
        addr = set()
        for _, msg in msgs:
            for x in re.findall('<\w+@gmail\.com>', str(msg)):
                addr.add(x)
        return {x[1:-1] for x in addr} 

class FacebookSession(WebSession):
    '''Session for Facebook. Check attribute METHODS for methods it supports.'''

    # Constant values of FacebookSession
    HOME = 'https://m.facebook.com/'
    PROF = HOME + 'profile.php' 
    TABS = 'timeline friends info photos likes followers'.split()
    INFO_ATTRS = 'Mobile Address Facebook Birthday Gender Languages Hometown'.split()
    METHODS = 'add id_from_vanity vanity_from_id async_retrieval friends friends_of_friends info likes shares'.split()

    def __init__(self, login, passwd, db=list()):
        self.login  = login
        self._vn_to_id = dict()
        self._id_to_vn = dict()
        url = self.HOME + 'login.php'
        params = {'fb_noscript':'0', 'email':login, 'pass':passwd}
        try:
            self.initialize(url_login=url, url_auth=url, params=params) 
            soup = BS(self.access(self.HOME), PARSER)
            self.userID = soup.find('input', attrs={'name' : 'target'})['value']
            print('Logged in to %s' % self.userID)
        except (KeyError, ConnectionError, TypeError):
            raise AuthenticationError
        for personID, vanity in db:
            self.add(personID, vanity)

    def add(self, personID, vanity):
        '''Update cache for id <-> vanity'''
        self._vn_to_id[vanity] = personID
        self._id_to_vn[personID] = vanity

    def profile(self, personID, tab):
        assert tab in self.TABS
        return self.access(self.PROF, params={'id':personID, 'v':tab})

    def _id_from_document(self, doc):
        '''Primitive method: return personID from a document'''
        # Do not use Regex as it is slow.
        start = doc.find('/messages/thread/')
        end   = doc.find('/"', start)
        personID = doc[start + 17 : end]
        return personID

    def _link_from_vanity(self, vanity):
        return '%s%s?v=following' % (self.HOME, vanity)

    def id_from_vanity(self, vanity):
        ''' Return personID from given vanity.
            Significantly slower than its inverse.
        '''
        if vanity in self._vn_to_id:
            return self._vn_to_id[vanity]
        doc = self.access(self._link_from_vanity(vanity))
        if doc is None:
            return None
        personID = self._id_from_document(doc)
        self.add(personID, vanity)
        return personID
    
    def vanity_from_id(self, personID):
        ''' Return vanity from given personID.
            Significantly faster than its inverse.
        '''
        if personID in self._id_to_vn:
            return self._id_to_vn[personID]
        DESK_PROF = 'https://www.facebook.com/profile.php'
        resp = self.session.head(DESK_PROF, params={'id': personID})
        vanity = resp.headers['location'][25:] if resp.is_redirect else None 
        self.add(personID, vanity)
        return vanity 
    
    def async_retrieval(self, links, function):
        ''' Note: this function is asynchronous. Therefore the order of
            operations is indeterminate but is faster. Useful for both
            computationally and I/O intensive tasks.
        '''
        from aiohttp import ClientSession
        from asyncio import get_event_loop
        stuffs = list()
        async def helper(client):
            for link in links:
                async with client.get(link) as web_html:
                    doc = await web_html.text()
                    stuffs.append(function(doc))
            await client.close()
        cookies = requests.utils.dict_from_cookiejar(self.session.cookies)
        task = helper(ClientSession(cookies=cookies))
        get_event_loop().run_until_complete(task)
        return stuffs

    def _friends_document_from_tab(self, personID, mutual, startindex):
        '''Primitive method: return HTML from Friends Tab'''
        return self.access(self.PROF, {'v':'friends', 'id':personID, 'mutual':mutual, 'startindex':startindex})

    def _friends_from_tab(self, personID, mutual, startindex):
        '''Primitive method: return (ids, vns) from Friends Tab'''
        doc = self._friends_document_from_tab(personID, mutual, startindex)
        id_regex = '\/profile.php\?id=([0-9]*)\&fref'
        vn_regex = '\/([a-zA-Z0-9\.]*)\?fref'
        ids, vns = list(), list()
        soup = BS(doc, PARSER)
        for x in soup('a'):
            s = x.get('href', str())
            idr = re.match(id_regex, s)
            vnr = re.match(vn_regex, s)
            if idr:
                ids.append(idr.group(1))
            elif vnr:
                vns.append(vnr.group(1))
        return (ids, vns) 

    def _number_of_friends_of(self, personID, mutual):
        '''Primitive method'''
        doc = self._friends_document_from_tab(personID, mutual, 0)
        res = re.search('Friends\s\(([0-9\,]*)\)', doc)
        grp = res.group(1).replace(',','') 
        return int(grp)

    def info(self, personID):
        ''' Return a dictionary with all elements of INFO_ATTRS as keys.'''
        soup = BS(self.profile(personID, 'info'), PARSER)
        info = dict()

        def fn(string, attribute):
            # Handles different attributes accordingly
            q = utils.remove_substr(string, attribute)
            d = {'Birthday' : utils.Birthdate, 
                 'Facebook' : utils.drop_two,
                 'Languages': utils.list_langs}
            if attribute not in d:
                return q
            return d[attribute](q)

        for attribute in self.INFO_ATTRS:
            query = soup.find('div', attrs={'title' : attribute})
            info[attribute.lower()] = None if query is None else fn(query.text, attribute)
        info['name'] = soup.title.text
        return info

    def likes(self, personID):
        ''' Return a set of names of pages liked by personID
            Facebook has different profile IDs for
            equivalent or similar pages.
        '''
        soup = BS(self.profile(personID, 'likes'), PARSER)
        extras = [soup.title.text, 'See more', '', 'Ask', 'Request sent', 'AskRequest sent']
        return {t for t in map(lambda s: s.text, soup('span')) if t not in extras}

    def shares(self, personID):
        ''' Return a list of lists of people whom personID
            shared anything with. Currently only support front page.
        '''
        soup = BS(self.profile(personID, 'timeline'), PARSER)
        browse_regex = '\/browse\/users\/\?ids=([0-9C%]*)\&' 
        res = (re.match(browse_regex, t) for t in map(lambda x: x.get('href'), soup('a')) if t is not None)
        return [s.group(1).split('%2C') for s in res if s]

    def is_private(self, personID):
        '''Return whether friend list of personID is private or not.'''
        p, q = self._friends_from_tab(personID, False, 1)
        return not (p or q)

    def friends(self, personID, mutual=False, translate=True):
        ''' Return friends from personID
            mutual=False returns all friends of personID, and
            empty list if is_private(personID)
            translating all vanities to IDs can be slow.
        '''
        NFD = 24 # Number of friends displayed if include non-mutuals.
        FPP = 36 # Friends per page
        cids, cvns = list(), list()
        if self.is_private(personID) and not mutual:
            return list()
        num = self._number_of_friends_of(personID, mutual)
        for pg in itertools.chain([0], itertools.count(FPP if mutual else NFD, FPP)):
            if pg > num:
                return cids + [self.id_from_vanity(vn) for vn in cvns] if translate else (cids, cvns) 
            ids, vns = self._friends_from_tab(personID, mutual=mutual, startindex=pg)
            cids.extend(ids)
            cvns.extend(vns)
