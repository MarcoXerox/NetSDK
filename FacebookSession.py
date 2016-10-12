import re, itertools, utils, Base
from bs4 import BeautifulSoup as BS

class FacebookSession(Base.WebSession):
    ''' Session for Facebook. Check attribute METHODS for methods it supports.
        FacebookHandle comes with multisession support.
    '''

    # Constant values of FacebookSession
    HOME = 'https://m.facebook.com/'
    PROF = HOME + 'profile.php' 
    TABS = 'timeline friends info photos likes followers'.split()
    INFO_ATTRS = 'Mobile Address Facebook Birthday Gender Languages Hometown'.split()
    METHODS = 'log_out profile is_private friends info likes shares'.split()

    def __init__(self, login, passwd):
        url = self.HOME + 'login.php'
        params = {'fb_noscript':'0', 'email':login, 'pass':passwd}
        super().__init__(url_login=url, url_auth=url, params=params) 

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
        start = doc.find('/mbasic/more/?owner_id=')
        end   = doc.find('"', start)
        return doc[start + 23 : end]
    
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

    def friends(self, personID, mutual=None):
        ''' How to optimize further? '''
        mutual = self.is_private(personID) if mutual is None else mutual
        NFD = 24 # Number of friends displayed if include non-mutuals.
        FPP = 36 # Friends per page
        doc = self._friends_document_from_tab(personID, mutual, 0)
        _n = re.search('Friends\s\(([0-9\,]*)\)', doc)
        if _n is None:
            return list()
        num = int(_n.group(1).replace(',',''))
        return self._friends_from_doc(doc) + [item for pg in range(FPP if mutual else NFD, num, FPP) for item in self._friends_from_tab(personID, mutual, pg)]

    def _friends_from_tab(self, personID, mutual, startindex):
        ''' _friends_from_tab = _friends_from_doc . _friends_document_from_tab '''
        return self._friends_from_doc(self._friends_document_from_tab(personID, mutual, startindex))

    def _friends_from_doc(self, document):
        soup = BS(document, Base.PARSER)
        add_friend = '/a/mobile/friends/add_friend.php?id='
        id_prefix = '/profile.php?id='
        
        results = list() 
        for x in soup('table')[1:-4]:
            try:
                name = x.img['alt']
                vnORid, *MaybeID = [y['href'] for y in x('a')]
            except (TypeError, KeyError):
                continue
            pid = MaybeID.pop() if MaybeID else None
            personID = None
            if pid is not None and pid.startswith(add_friend):
                amp_idx = pid.find('&')
                personID = pid[36:amp_idx]
            vanity = vnORid[1:vnORid.find('?fref')]
            correct = '/' not in vanity and '?' not in vanity
            result = None
            if vnORid.startswith(id_prefix):
                result = (name, vnORid[16:-21], None)
            elif correct:
                result = (name, personID, vanity)
            if result is not None:
                results.append(result)
        return results

    def info(self, personID):
        ''' Return a dictionary with all elements of INFO_ATTRS as keys.'''
        soup = BS(self.profile(personID, 'info'), Base.PARSER)
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
        soup = BS(self.profile(personID, 'likes'), Base.PARSER)
        extras = [soup.title.text, 'See more', '', 'Ask', 'Request sent', 'AskRequest sent']
        return {t for t in map(lambda s: s.text, soup('span')) if t not in extras}

    def shares(self, personID):
        ''' Return a list of lists of people whom personID
            shared anything with. Currently only support front page.
        '''
        soup = BS(self.profile(personID, 'timeline'), Base.PARSER)
        browse_regex = '\/browse\/users\/\?ids=([0-9C%]*)\&' 
        res = (re.match(browse_regex, t) for t in map(lambda x: x.get('href'), soup('a')) if t is not None)
        return [s.group(1).split('%2C') for s in res if s]

    def is_private(self, personID):
        '''Return whether friend list of personID is private or not.'''
        return not self._friends_from_tab(personID, False, 1)
