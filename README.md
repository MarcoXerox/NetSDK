# NetSDK
A open-source library released under GPLv3 for various platforms by web scrapping.
Currently support Google and Facebook Login. In addition, Facebook Session supports scrapping friends and personal information from a valid FB Account. Note that this is against Facebook Terms of Service and is intended for demonstration purposes only.

### Features
**NetSDK** refrains from using `selenium` or `mechanize` to scrap info, unlike similar projects such as `fb-hfc`. Hence, **NetSDK** is much simpler and faster by avoiding Javascript and thus AJAX.

### Installation
**NetSDK** depends on 
  - Python 3.5 (for async)
  - python3-requests
  - python3-aiohttp

If your system do not have `pip3`, refer to this guide: https://docs.python.org/3/installing/

Otherwise, simply run `sudo pip3 install requests aiohttp` to satisfy dependencies.

### Documentation
Most functions come with **NetSDK** have docstrings. **NetSDK** sessions contain an attribute `METHODS` giving a list of methods the session supports.

`GoogleSession` supports `addresses` which give a set of addresses from which the account receives mail.
`FacebookSession` supports the following:
  - `info`, `likes` and `shares`: personal info
  - `friends`: a list of friends
  - `id_from_vanity`, `vanity_from_id`: translating between vanity (username) and Facebook ID
  - `async_retrieval`: friendly interface to finish I/O and computationally intensive tasks quickly.
