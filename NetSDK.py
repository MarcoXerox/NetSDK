import re, requests, imaplib, itertools, multiprocessing
import utils
from bs4 import BeautifulSoup as BS
PARSER = 'html.parser'

class AuthenticationError(Exception):
    '''Wrong credentials submitted''' 

class WebSession(object):
    '''Generic class of a web session'''
    METHODS = 'initialize access from_cookies'.split()

    def initialize(self, url_login, url_auth, params=dict()):
        '''Session initialization'''
        self.session = requests.session()
        web_html = self.session.get(url_login)
        soup = BS(web_html.content, PARSER).find('form').find_all('input')
        cred = {x['name'] : x['value'] for x in soup if x.has_attr('value')}
        cred.update(params)
        self.session.post(url_auth, data=cred)

    def access(self, url, params=dict()):
        ''' Issue a GET request for body of url. 
            Return None if access failed.
        '''
        g = self.session.get(url, params=params)
        if g.status_code == 200:
            return g.text
        return None

    @classmethod
    def from_cookies(cls, cookies):
        self.session = requests.session(cookies=cookies)

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
    ''' Session for Facebook. Check attribute METHODS for methods it supports.
        FacebookHandle comes with multisession support.
    '''

    # Constant values of FacebookSession
    HOME = 'https://m.facebook.com/'
    PROF = HOME + 'profile.php' 
    TABS = 'timeline friends info photos likes followers'.split()
    INFO_ATTRS = 'Mobile Address Facebook Birthday Gender Languages Hometown'.split()
    METHODS = 'id_from_vanity vanity_from_id friends info likes shares'.split()

    def __init__(self, login, passwd):
        url = self.HOME + 'login.php'
        params = {'fb_noscript':'0', 'email':login, 'pass':passwd}
        self.initialize(url_login=url, url_auth=url, params=params) 

    def log_out(self):
        doc = self.access(self.HOME)
        start = doc.find('/logout.php')
        end = doc.find('">', start)
        self.session.post(self.HOME + doc[start : end])

    def profile(self, personID, tab):
        ''' Shortcut to access profile '''
        assert tab in self.TABS
        return self.access(self.PROF, params={'id':personID, 'v':tab})

    def id_from_vanity(self, vanity):
        ''' Return personID from given vanity.
            Significantly slower than its inverse.
        '''
        doc = self.access('%s%s?v=following' % (self.HOME, vanity))
        if doc is None: return None
        start = doc.find('/messages/thread/')
        end   = doc.find('/"', start)
        return doc[start + 17 : end]
    
    def vanity_from_id(self, personID):
        ''' Return vanity from given personID.
            Significantly faster than its inverse.
        '''
        DESK_PROF = 'https://www.facebook.com/profile.php'
        resp = self.session.head(DESK_PROF, params={'id': personID})
        return resp.headers['location'][25:] if resp.is_redirect else None 
    
    def _friends_document_from_tab(self, personID, mutual, startindex):
        '''Primitive method: return HTML from Friends Tab'''
        return self.access(self.PROF, {'v':'friends', 'id':personID, 'mutual':mutual, 'startindex':startindex})

    def _number_of_friends_of(self, personID, mutual):
        ''' Primitive method: return number of friends as counted by Facebook. 
            Always not less than actual number of friends found. Can be used as estimate.
        '''
        doc = self._friends_document_from_tab(personID, mutual, 0)
        res = re.search('Friends\s\(([0-9\,]*)\)', doc)
        grp = res.group(1).replace(',','') 
        return int(grp)

    def friends(self, personID, mutual=False):
        ''' Return friends from personID
            When mutual is False, friends return
                public:  all friends of personID
                private: empty list 
        '''
        NFD = 24 # Number of friends displayed if include non-mutuals.
        FPP = 36 # Friends per page
        id_regex = '\/profile.php\?id=([0-9]*)\&fref'
        vn_regex = '\/([a-zA-Z0-9\.]*)\?fref'
        ids, vns = list(), list()
        if self.is_private(personID) and not mutual:
            return list()
        num = self._number_of_friends_of(personID, mutual)
        for pg in itertools.chain([0], itertools.count(FPP if mutual else NFD, FPP)):
            if pg > num:
                return (ids, vns) 
            soup = BS(self._friends_document_from_tab(personID, mutual, startindex), PARSER)
            for x in soup('a'):
                s = x.get('href', str())
                idr = re.match(id_regex, s)
                vnr = re.match(vn_regex, s)
                if idr:
                    ids.append(idr.group(1))
                elif vnr:
                    vns.append(vnr.group(1))

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

class FacebookHandle(object):
    ''' Provides multisession support.
        Data of solving 105 vanities, inclusive of login time:
            size=01:  80s
            size=04:  32s
            size=08:  35s
        Data of solving 570 vanities, exclusive of login time: 
            size=04: 120s 
            size=16:  36s
            size=32:  32s
        Use appropriate number of threads hence.
    '''
    METHODS = FacebookSession.METHODS + ['add', 'do']

    def __init__(self, login, passwd, cookies=None, size=8):
        ''' Initialize clients '''

        self.size = size
        self._vn_to_id = dict()
        self._id_to_vn = dict()

        try:
            self.test = FacebookSession(login, passwd)
            soup = BS(self.test.access(self.test.HOME), PARSER)
            self.userID = soup.find('input', attrs={'name' : 'target'})['value']
        except (KeyError, ConnectionError, TypeError):
            raise AuthenticationError
        
        if cookies is None or len(cookies) > size:
            import progressbar
            bar = progressbar.ProgressBar()
            self.clients = list()
            for _ in bar(range(size)):
                self.clients.append(FacebookSession(login, passwd))
        else:
            self.clients = [FacebookSession.from_cookies(c) for c in cookies[:size]]

    def close(self, *exc):
        ''' Simulate log out of clients '''
        self.test.log_out()
        import progressbar
        bar = progressbar.ProgressBar()
        for client in bar(self.clients):
            client.log_out()

    def add(self, personID, vanity):
        ''' Cache (personID, vanity) pairs '''
        self._vn_to_id[vanity] = personID
        self._id_to_vn[personID] = vanity

    def export(self):
        ''' Return (List of (ID, vanity), List of cookie dictionaries) '''
        return list(_id_to_vn.items()), [requests.utils.dict_from_cookiejar(client.session.cookies) for client in self.clients]

    def id_from_vanity(self, vanity):
        try:
            return self._vn_to_id[vanity]
        except KeyError:
            personID = self.test.id_from_vanity(vanity)
            self.add(personID, vanity)
            return personID 

    def vanity_from_id(self, personID):
        try:
            return self._id_to_vn[personID]
        except KeyError:
            vanity = self.test.vanity_from_id(personID)
            self.add(personID, vanity)
            return vanity

    friends = lambda self: self.test.friends
    info    = lambda self: self.test.info
    links   = lambda self: self.test.links
    shares  = lambda self: self.test.shares

    def _map_function_to_client_and_list(self, pair):
        ''' Primitive method. Raise AttributeError if client lacks function. '''
        client, xs = pair
        return [self.function(client, x) for x in xs]

    def do(self, function, xs):
        ''' Map a function to every element of xs and return the result. '''
        if self.size <= 0:
            raise ValueError
        self.function = function
        chunks, rems  = utils.slice_to_chunks_and_rems(xs, self.size)
        with multiprocessing.Pool(self.size) as p:
            return p.map(self._map_function_to_client_and_list, zip(self.clients, chunks)) + [function(self.test, x) for x in rems]
