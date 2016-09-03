import enum

# Data types
Month = enum.Enum('Month', 'January February March April May June July August September October November December')

class Birthdate(object):
    def __init__(self, bstring, year=2000):
        self.is_nil = bstring is None
        if not self.is_nil:
            date, *yr  = bstring.split(', ')
            month, day = date.split()
            self.year  = int(yr.pop() if yr else year)
            self.month = Month[month]
            self.day   = int(day)
    def __repr__(self, sep='/'):
        if self.is_nil:
            return 'None'
        return '%d%c%02d%c%02d' % (self.year, sep, self.month.value, sep, self.day)
    def __eq__(self, other):
        if self.is_nil and other_isnil:
            return True
        return self.year == other.year and self.month == other.month and self.day == other.day

# Helper functions
def remove_substr(old, rep):
    return old.replace(rep, '')

def list_langs(string):
    if string is None:
        return list()
    *s, e = string.split(', ')
    return s + e.split(' and ')

def drop_two(lst):
    return lst[2:]

# Abstract type to store data
class VNIDS(object):
    def __init__(self, isID, string):
        self.isID = isID
        self.string = string
    def __repr__(self):
        return '<%s> %s' % ('ID' if self.isID else 'VN', self.string)
    def __eq__(self, other):
        return self.string == other.string
