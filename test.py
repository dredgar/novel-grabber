from nvg import *

for x in ['tieba', 'yamibo', 'nyasama']:
    load_cookies(f'{x}-cookies.json', x)

generate_collection([Nyasama(x) for x in [49451, 30279]], 'test.txt', 'number')
