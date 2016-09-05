# NetSDK (alpha 0.1.0)
A open-source library released under GPLv3 for various platforms by web scrapping.
Currently support Google and Facebook Login. In addition, Facebook Session supports scrapping friends and personal information from a valid FB Account. Note that this is against Facebook Terms of Service and is intended for demonstration purposes only.

### Features
**NetSDK** refrains from using `selenium` or `mechanize` to scrap info, unlike similar projects such as `fb-hfc`. Hence, **NetSDK** is much simpler and faster by avoiding Javascript and thus AJAX. **NetSDK** also supports well-tested multithreading: it translates Facebook IDs to usernames roughly 0.1s each.

### Installation
**NetSDK** depends on 
  - Python 3
  - python3-requests
  - python3-progressbar2 (optional)

If your system do not have `pip3`, refer to this guide: https://docs.python.org/3/installing/

Otherwise, simply run `sudo pip3 install requests aiohttp` to satisfy dependencies.

### Documentation
Most functions come with **NetSDK** have docstrings. **NetSDK** sessions contain an attribute `METHODS` giving a list of methods the session supports.

`GoogleSession` supports `addresses` which give a set of addresses from which the account receives mail.
`FacebookSession` supports the following:
  - `info`, `likes` and `shares`: personal info
  - `friends`: a list of friends
  - `id_from_vanity`, `vanity_from_id`: translating between vanity (username) and Facebook ID
  - `log_out`: simulate log out
`FacebookHandle` supports all methods of `FacebookSession` along with the following:
  - `add`: add more `(personID, vanity)` pair to cache
  - `do`: run a function with many threads
  - `close`: log out all client sessions
