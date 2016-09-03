import re, requests, imaplib, itertools
import utils
from bs4 import BeautifulSoup as BS
PARSER = 'html.parser'

class AuthenticationError(Exception):
    '''Wrong credentials submitted''' 

class WebSession(object):

    def __init__(self, login, url_login, url_auth, login_field_name, passwd_field_name):
        '''Generic Method for overriding'''
        self.url_login = url_login
        self.url_auth  = url_auth
        self.login_field_name  = login_field_name
        self.passwd_field_name = passwd_field_name 
        self.login  = login
        self.passwd = passwd

    def initialize(self, passwd, no_script_field=None, no_script_value=None):
        '''Session initialization'''
        self.session = requests.session()
        web_html = self.session.get(self.url_login)
        soup = BS(web_html.content, PARSER).find('form').find_all('input')
        cred = dict()
        for x in soup:
            if x.has_attr('value'):
                cred[x['name']] = x['value']
        if (no_script_field is not None and
            no_script_value is not None):
           cred[no_script_field] = no_script_value
        cred[self.login_field_name]  = self.login
        cred[self.passwd_field_name] = passwd
        self.session.post(self.url_auth, data=cred)

    def access(self, URL, params={}):
        '''Access URL in current session'''
        return self.session.request('GET', URL, params=params).text

class GoogleSession(WebSession):

    url_login = 'https://accounts.google.com/ServiceLogin'
    url_auth  = 'https://accounts.google.com/ServiceLoginAuth'
    login_field_name  = 'Email'
    passwd_field_name = 'Passwd' 

    GMAIL = 'https://mail.google.com'

    def __init__(self, login, passwd):
        self.login  = login
        self.initialize(passwd)
        if login not in self.access(self.GMAIL):
            raise AuthenticationError

    @property
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
    '''Interface for GET/POST in Facebook'''

    # Constant values of FacebookSession
    HOME = 'https://m.facebook.com'
    PROF = HOME + '/profile.php' 
    TABS = 'timeline friends info photos likes following'.split()
    INFO_ATTRS = 'Mobile Address Facebook Birthday Gender Languages Hometown'.split()

    # Constants for superclass
    url_login = HOME + '/login.php'
    url_auth  = HOME + '/login.php'
    login_field_name  = 'email'
    passwd_field_name = 'pass' 

    def __init__(self, login, passwd, vndict=dict()):
        self.login  = login
        self.vndict = vndict 
        self._userID = None
        try:
            self.initialize(passwd, no_script_field='fb_noscript', no_script_value='0')
            print('Logged in to %s' % self.userID)
        except (KeyError, ConnectionError, TypeError):
            raise AuthenticationError

    @property
    def userID(self):
        '''Return the session user's ID'''
        if self._userID is None:
            soup = BS(self.access(self.HOME), PARSER)
            self._userID = soup.find('input', attrs={'name' : 'target'})['value']
        return self._userID

    def id_from_vanity(self, vanity):
        '''Return personID from given vanity'''
        if vanity in self.vndict:
            return self.vndict[vanity]
        doc = self.access(self.HOME + '/' + vanity)
        # Do not use Regex as it is slow.
        start = doc.find('/messages/thread/')
        end   = doc.find('/?', start)
        personID = doc[start + 17 : end]
        self.vndict[vanity] = personID
        return personID

    def id_from_VNIDS(self, s):
        return s.string if s.isID else self.id_from_vanity(s.string)

    def _friends_document_from_tab(self, personID, mutual, startindex):
        '''Primitive method: return HTML from Friends Tab'''
        return self.access(self.PROF, params={'v':'friends', 'id':personID, 'mutual':int(mutual), 'startindex':startindex})

    def _friends_from_tab(self, personID, mutual, startindex):
        '''Primitive method: return (vanities, ids) from Friends Tab'''
        doc = self._friends_document_from_tab(personID, mutual, startindex)
        id_regex = '\/profile.php\?id=([0-9]*)\&fref'
        vn_regex = '\/([a-zA-Z0-9\.]*)\?fref'
        friends  = list()
        soup = BS(doc, PARSER)
        for x in soup('a'):
            s = x.get('href', str())
            idr = re.match(id_regex, s)
            vnr = re.match(vn_regex, s)
            if idr:
                friends.append(utils.VNIDS(True, idr.group(1)))
            elif vnr:
                friends.append(utils.VNIDS(False, vnr.group(1)))
        return friends

    def _number_of_friends_of(self, personID, mutual):
        '''Primitive method'''
        return int(re.search('Friends\s\(([0-9\,]*)\)', self._friends_document_from_tab(personID, mutual, 0)).group(1).replace(',','')) 

    def info_of(self, personID):
        '''Return an Info object of ID'''        
        soup = BS(self.access(self.PROF, params={'v':'info', 'id':personID}), PARSER)
        info = dict()

        def fn(string, attribute):
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

    def is_private(self, personID):
        return not self._friends_from_tab(personID, False, 1)

    def friends_of(self, personID, mutual=False):
        '''Return friends from personID'''
        NFD = 24 # Number of friends displayed if include non-mutuals.
        FPP = 36 # Friends per page
        friends = list()
        if self.is_private(personID) and not mutual:
            return list()
        num = self._number_of_friends_of(personID, mutual)
        for pg in itertools.chain([0], itertools.count(FPP if mutual else NFD, FPP)):
            if pg > num:
                return friends
            friends.extend(self._friends_from_tab(personID, mutual=mutual, startindex=pg))
