import Base
from bs4 import BeautifulSoup as BS
from FacebookSession import FacebookSession

class FacebookHandle(Base.WebHandle, FacebookSession):
    ''' Main API 
        Provides cache and functions over all clients
    '''
    # Note: multiple inheritance is in place such that
    # every feature from FacebookSession is accessible
    # by the Handle, instead of a bunch of lambdas
    # replacing the original methods.

    METHODS = FacebookSession.METHODS + Base.WebHandle.METHODS + 'close ids_from_vanities'.split() 

    def __init__(self, login, passwd, cookies=None, size=8):

        self._vn_to_id = dict()
        self._id_to_vn = dict()
        self._vn_to_nm = dict()
        self._id_to_nm = dict()

        try:
            Base.WebHandle.__init__(self, FacebookSession, size)
            FacebookSession.__init__(self, login, passwd)
            soup = BS(self.access(self.HOME), Base.PARSER)
            self.userID = soup.find('input', attrs={'name' : 'target'})['value']
            self.userVN = self.vanity_from_id(self.userID)
            self.init_clients(login, passwd, cookies)
        except (KeyError, ConnectionError, TypeError):
            raise Base.AuthenticationError

    def close(self):
        ''' Simulate log out of clients '''
        self.log_out()
        for client in self.clients:
            client.log_out()

    def add(self, personID, vanity):
        ''' Cache (personID, vanity) pairs '''
        self._vn_to_id[vanity] = personID
        self._id_to_vn[personID] = vanity

    def id_from_vanity(self, vanity):
        try:
            return self._vn_to_id[vanity]
        except KeyError:
            personID = FacebookSession.id_from_vanity(self, vanity)
            self.add(personID, vanity)
            return personID 

    def vanity_from_id(self, personID):
        try:
            return self._id_to_vn[personID]
        except KeyError:
            vanity = FacebookSession.vanity_from_id(self, personID)
            self.add(personID, vanity)
            return vanity

    def ids_from_vanities(self, vanities):
        ''' Use this instead of [self.id_from_vanity(v) for v in vanities] '''
        located, rest, personIDs = list(), list(), list()
        for vanity in vanities:
            try:
                personID = self._vn_to_id[vanity]
                located.append(vanity)
                personIDs.append(personID)
            except KeyError:
                rest.append(vanity)
        personIDs.extend(self.multimap(FacebookSession.id_from_vanity, rest))
        for personID, vanity in zip(personIDs, located + rest):
            self.add(personID, vanity)
        return personIDs

    def friends(self, personID, mutual=None):
        ''' Return (IDs, VNs) 
            Names extracted are stored
        '''
        return self._arrange_friends(FacebookSession.friends(self, personID, mutual))

    def _arrange_friends(self, frds, signal=True):
        ids, vns = list(), list()
        for name, MaybeID, MaybeVN in frds:
            if MaybeID is not None and MaybeVN is not None:
                self.add(MaybeID, MaybeVN)
                self._id_to_nm[MaybeID] = name
                self._vn_to_nm[MaybeVN] = name
            if MaybeID:
                ids.append(MaybeID)
                self._id_to_nm[MaybeID] = name
            elif MaybeVN:
                vns.append(MaybeVN)
                self._vn_to_nm[MaybeVN] = name
            elif signal:
                raise Base.URLError
        return ids, vns

    def friends_of_friends(self, personID):
        ids, vns = self.friends(personID)
        ids.extend(self.ids_from_vanities(vns))
        res = self.multimap(FacebookSession.friends, ids)
        ans = dict()
        for friendID, frds in zip(ids, res):
            pids, pvns = self._arrange_friends(frds)
            pids.extend(self.ids_from_vanities(vns))
            ans[friendID] = [personID for personID in pids if len(personID) < 20] # Constant is arbitrary 
        return ans

    def network(self, personID):
        ''' Find the friend network of personID effectively. '''
