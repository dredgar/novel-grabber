from nvg import *

load_tieba_cookies('tieba-cookies.json')
load_yamibo_cookies('yamibo-cookies.json')

generate_collection([Yamibo(x) for x in (
    87560,
    159379,
    )], 'test.txt', 'number')
