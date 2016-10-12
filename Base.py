import requests, multiprocessing, time
import utils
from bs4 import BeautifulSoup as BS
PARSER = 'html.parser'

'''
Solving 105 FB usernames
size=01:  80s
size=04:  32s
size=08:  35s
Solving 570 FB usernames 
size=04: 120s 
size=16:  36s
size=32:  32s
'''

class AuthenticationError(Exception):
    '''Wrong credentials submitted''' 

class URLError(Exception):
    '''URL failed to retrieve appropriate content''' 

class WebSession(object):
    '''Generic class of a web session'''
    METHODS = 'access from_cookies'.split()

    def __init__(self, url_login, url_auth, params=dict(), agent=None):
        '''Session initialization'''
        self.session = requests.session()
        web_html = self.session.get(url_login)
        soup = BS(web_html.content, PARSER).find('form').find_all('input')
        cred = {x['name'] : x['value'] for x in soup if x.has_attr('value')}
        cred.update(params)
        if agent is not None:
            self.session.headers.update({'user-agent':agent})
        self.session.post(url_auth, data=cred)

    def access(self, url, params=dict()):
        ''' Issue a GET request for body of url. ''' 
        g = self.session.get(url, params=params)
        if g.ok:
            return g.text
        raise URLError

    @classmethod
    def from_cookies(cls, cookies):
        self.session = requests.session(cookies=cookies)

class WebHandle(object):
    ''' Provides multisession support. '''
    METHODS = 'init_clients export_cookies multimap'.split()
    DELAY = 0.75
    
    def __init__(self, session_type, size):
        ''' Initialize clients '''
        self.session_type = session_type
        self.size = size

    def init_clients(self, login, passwd, cookies):
        self.clients = list() if cookies is None else [self.session_type.from_cookies(c) for c in cookies[:self.size]]
        num_of_logins = self.size - len(self.clients)
        try:
            import progressbar
            bar = progressbar.ProgressBar(max_value=num_of_logins)
        except ImportError:
            pass    
        for _ in range(num_of_logins):
            self.clients.append(self.session_type(login, passwd))
            time.sleep(self.DELAY)
            try:
                bar.update(bar.value + 1)
            except NameError:
                pass

    def export_cookies(self):
        return [requests.utils.dict_from_cookiejar(client.session.cookies) for client in self.clients]

    def _map_function_to_client_and_list(self, pair):
        ''' Primitive method. Raise AttributeError if client lacks function. '''
        client, xs = pair
        return [self._fn(client, x) for x in xs] 

    def multimap(self, session_function, xs):
        ''' Map a function to every element of xs and return the result. ''' 
        if self.size <= 0:
            raise ValueError
        chunks, rems = utils.slice_to_chunks_and_rems(xs, self.size)
        self._fn = session_function
        results = [session_function(self, x) for x in rems]
        with multiprocessing.Pool(self.size) as p:
            for solved in p.map(self._map_function_to_client_and_list, zip(self.clients, chunks)):
                results.extend(solved)
        return results

