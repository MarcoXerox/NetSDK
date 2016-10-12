import imaplib
import Base

class GoogleSession(Base.WebSession):
    '''Session for Google'''

    GMAIL = 'https://mail.google.com'
    METHODS = ['addresses']

    def __init__(self, login, passwd):
        self.login = login
        cred = {'Email':login, 'Passwd':passwd}
        super().__init__(
                url_login='https://accounts.google.com/ServiceLogin', 
                url_auth ='https://accounts.google.com/ServiceLoginAuth',
                params=cred)
        if login not in self.access(self.GMAIL):
            raise Base.AuthenticationError

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
