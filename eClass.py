import re, Base
from bs4 import BeautifulSoup as BS

# Constants
NUM_PAGE = 200 
UNSIGNED = 'Unsigned'
USERNAME_ID = 'UserLogin'
PASSWORD_ID = 'UserPassword'
LOGINBTN_ID = 'login_btn'
LOGIN_SUCCESS_TITLE = 'eClass IP 2.5'
LOGIN_FAILURE_TITLE = 'eClass Integrated Platform 2.5' 
USER_AGENT  = 'Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.1453.94 Safari/537.36'
NOTICE_LINK = 'tablebluelink'
ECLASS   = 'https://eclass.lasalle.edu.hk'
ENOTICE  = ECLASS + '/home/eService/notice/student_notice'
ELOGIN   = ECLASS + '/login.php'
UNEXPIRED, ALL_NOTICE, EXPIRED = 0, 1, 2
ALL_STATUS, NOT_SIGNED, SIGNED = 0, 1, 2
# Other parameters to eNotice: keyword, order, year (>2012), month, field

class eClassSession(Base.WebSession):
    ''' Session for eClass IP 2.5 '''
    METHODS = ['sign_all']

    def __init__(self, login, passwd):
        link = '%s/index.php?page_size_change=1&noticeType=%d&signStatus=%d&numPerPage=%d' % (ENOTICE, EXPIRED, NOT_SIGNED, NUM_PAGE)
        cred = {USERNAME_ID:login, PASSWORD_ID:passwd}
        super().__init__(url_login=ECLASS, url_auth=ELOGIN, params=cred, agent=USER_AGENT)
        self.notice = self.access(link)
        if LOGIN_FAILURE_TITLE in self.notice:
            raise Base.AuthenticationError

    def sign_all(self):
        for element in BS(self.notice, Base.PARSER).find_all(class_=NOTICE_LINK):
            if UNSIGNED not in element.text:
                self.session.post(re.sub(r'^javascript:sign\((\d+)\,(\d+)\)$', r'%s/sign_update.php?NoticeID=\1&StudentID=\2' % ENOTICE, element['href']))
