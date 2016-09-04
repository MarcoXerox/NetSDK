import enum

# Test suite
CHAR_1 = '100003266237998' # Private friends list
CHAR_2 = '100002538713682' # Large friend list
CHAR_3 = '100008209237246' # No vanity

# Data types
Month = enum.Enum('Month', 'January February March April May June July August September October November December')

class Birthdate(str):
    def __init__(self, bstring, year=2000):
        date, *yr  = bstring.split(', ')
        month, day = date.split()
        self.year  = int(yr.pop() if yr else year)
        self.month = Month[month]
        self.day   = int(day)
    def __repr__(self, sep='/'):
        return '%d%s%02d%s%02d' % (self.year, sep, self.month.value, sep, self.day)
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
