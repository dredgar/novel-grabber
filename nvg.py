import os, json, time
import zhconv
import requests
import lxml.html as lh
from lxml.html.clean import clean_html
from html2text import HTML2Text
from requests_html import HTMLSession, HTML
from bs4 import BeautifulSoup as bs
from inscriptis import get_text

cookies = dict()
cache_path = 'cache'
if not os.path.exists(cache_path):
    os.makedirs(cache_path)

def fix_nl(s):
    return s if s.endswith('\n') else (s + '\n')
def split_lines(s):
    s = fix_nl(s)
    lines = []
    t = []
    for c in s:
        t.append(c)
        if c == '\n':
            lines.append(''.join(t))
            t.clear()
    return lines
'''
def process_text(s):
    s = zhconv.convert(fix_nl(s), 'zh-cn')
    lines = []
    t = split_lines(s)
    for r in t:
        if r == '\n':
            continue
        lines.append(r)
    t = [r for r in lines]
    lines = []
    ncnt = 0
    for line in t:
        if line == '\n':
            ncnt += 1
        else:
            lines.append(line)
            if ncnt > 1:
                lines.append('\n')
            ncnt = 0
    if ncnt > 1:
        lines.append('\n')
    # ncnt = 0
    return fix_nl(''.join(lines))
'''
def process_text(s):
    s = zhconv.convert(fix_nl(s), 'zh-cn')
    lines = (line.strip() for line in s.splitlines())
    # break multi-headlines into a line each
    # chunks = (phrase.strip() for line in lines for phrase in line.split('  '))
    # drop blank lines
    return '\n'.join(line for line in lines if line) + '\n'
def optimize_url(url):
    '''
    Convert a url to make it supported by Windows filesystem.
    '''
    url = url.replace('*', '')
    for x in ('/', '?', ':', '|', '\\', '<', '>'):
        url = url.replace(x, ' ')
    return ' '.join(url.split())
def ask_with_y(s):
    return input(s + ' (y)').lower() != 'n'
def ask_with_n(s):
    return input(s + ' (n)').lower() == 'y'
def check_refused_overwrite(url):
    return os.path.exists(url) and not ask_with_n('%s exists. Overwrite?' % url)

def read_cookies(url):
    '''
    Read cookies formatted for requests module from a file that EditThisCookie extension exports to.
    :param url: Path to the file EditThisCookie exported to.
    '''
    ret = dict()
    for x in json.load(open(url, 'r', encoding='utf-8')):
        ret[x['name']] = x['value']
    return ret
'''
def html_getter_2(cks):
    se = HTMLSession()
    return lambda url: se.get(url, cookies=cks).html
'''

class MaxTryLimitExceed(Exception):
    pass
def keep_trying(max_depth=5, catchee=BaseException):
    def decorater(func):
        def wrapper(args, kwargs, depth):
            if depth >= max_depth: raise MaxTryLimitExceed
            try:
                return func(*args, **kwargs)
            except catchee as e:
                print(f'In depth {depth}: {type(e).__name__}: {e}')
                return wrapper(args, kwargs, depth + 1)
        def handler(*args, **kwargs):
            return wrapper(args, kwargs, 0)
        return handler
    return decorater

class HTT(object):
    def __init__(self):
        self.h2t = HTML2Text()
        self.h2t.ignore_links = True
        self.h2t.ignore_images = True
    def __call__(self, html):
        ret = self.h2t.handle(html)
        if ret.strip().endswith('---'):
            ret = ret[:ret.rfind('---')]
        return ret
htt = HTT()

class Elem(object):
    def __init__(self, elem):
        self.data = elem
        '''
        if not self._text:
            self._text = htt(self.data.html) #.strip()
            # self._text = ''.join(bs(self.data.html, "html.parser").stripped_strings)
        return self._text
        '''
    @property
    def attrs(self):
        return self.data.attrs
    @property
    def text(self):
        return self.data.text
    @property
    def ptext(self):
        return htt(self.data.html)
    def find(self, word):
        return list(map(Elem, self.data.find(word)))
    def finds(self, word):
        return Elem(self.data.find(word, first=True))
    def findt(self, word):
        return self.finds(word).text

def html_getter(cks):
    return lambda url: Elem(HTML(html=requests.get(url, cookies=cks).text).find('html', first=True))

class BaseContent(object):
    '''
    Base novel content class.
    '''
    tid = ''
    title = ''
    txts = []
    site = ''
    author = ''

    def fetch(self):
        raise RuntimeError('fetch without specific site')
    def __init__(self, tid):
        self.tid = str(tid)
        cache_url = cache_path + '/%s_%s.json' % (self.site, self.tid)
        if os.path.exists(cache_url):
            data = json.load(open(cache_url, 'r', encoding='utf-8'))
            self.title = data['title']
            self.author = data['author']
            self.txts = data['txts']
            print(self.site, self.title, self.tid)
            print('Cache found.' if self.txts else 'Failed cache found.')
        else:
            while not self.txts:
                try:
                    keep_trying()(self.fetch)()
                except MaxTryLimitExceed:
                    if not ask_with_y('Failed, retry?'):
                        if not ask_with_n('Save failed cache?'):
                            return
                        self.txts = []
                        break
            json.dump(
                {'title': self.title, 'txts': self.txts, 'site': self.site, 'tid': self.tid, 'author': self.author}, 
                open(cache_url, 'w', encoding='utf-8'))
    def generate(self, split_mode='none', output_url=None, open_mode='w', if_optimize_url=True, if_attach_title=False):
        print("Generating %s.." % self.title)
        if not self.txts:
            print('Invalid one.')
            return
        txts = [fix_nl(s) for s in self.txts]
        s = ''
        if if_attach_title:
            s = '## %s\n' % self.title
        s += f'_From {self.site} {self.tid}_\n'
        if self.author:
            s += f'_By {self.author}_\n'
        if len(txts) > 1:
            if split_mode == 'none':
                s += '\n'.join(txts) + '\n'
            elif split_mode == 'spliter':
                s += '\n$$$$$$$$$$$$\n\n'.join(txts) + '\n'
            elif split_mode == 'first_line':
                s += '\n'.join(['### ' + txt for txt in txts]) + '\n'
            elif split_mode == 'number':
                for i in range(len(txts)):
                    s += '### %d.\n' % (i + 1) + txts[i] + '\n'
            else:
                raise ValueError('invalid split mode')
        else:
            s += '\n' + txts[0] + '\n'
        
        if output_url is None:
            output_url = '%s.txt' % self.title
        if if_optimize_url:
            output_url = optimize_url(output_url)
        if open_mode.startswith('w') and check_refused_overwrite(output_url):
            print('Aborting.')
            return
        with open(output_url, open_mode, encoding='utf-8') as f:
            f.write(process_text(s))

def load_cookies(url, site):
    cookies[site] = read_cookies(url)

def generate_collection(srcs, output_url, split_mode):
    output_url = optimize_url(output_url)
    if check_refused_overwrite(output_url):
        print('Aborting.')
        return
    with open(output_url, 'w', encoding='utf-8') as fp:
        fp.write(f'Generated at {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}\n')
    for x in srcs:
        x.generate(split_mode=split_mode, output_url=output_url, open_mode='a', if_optimize_url=False, if_attach_title=True)

'''
class YamiboNew(BaseContent):
    site = 'yamibo_new'
    def fetch(self):
        se = HTMLSession()
        url = 'https://www.yamibo.com'
        page = se.get(url + '/novel/%s' % self.tid).html
        self.title = htt(ffind(page, 'h3.col-md-12'))
        self.txts = [se.get(url + htt(c.find('a[href]', first=True).attrs['href'].html.find('#txt', first=True).find('.panel-body', first=True)) for c in page.find('div[data-key]')]
'''

class Yamibo(BaseContent):
    site = 'yamibo'
    formatter_tid = 'https://bbs.yamibo.com/thread-%s-1-1.html'
    formatter_tid_page = 'https://bbs.yamibo.com/thread-%s-%d-1.html'
    def fetch(self):
        get = html_getter(cookies[self.site])
        html = get(self.formatter_tid % self.tid)
        self.title = html.finds('h1.ts').text
        print(f'{self.site}, {self.title}, {self.tid}')
        try:
            pcnt = int(html.finds('div.pg > label > span[title]').attrs['title'][1:-1])
        except:
            pcnt = 1

        def parse(doc):
            return list(filter(lambda x: x.attrs['id'][5:].isnumeric(), doc.finds('#postlist').find('div[id^=post]')))

        posts = parse(html)
        for i in range(2, pcnt + 1):
            posts += parse(get(self.formatter_tid_page % (self.tid, i)))
            print('Page', i)

        self.txts = []
        lz = None
        flag = True

        for p in posts:
            div = p.find('.authi')
            author = div[0].text
            date = div[1].findt('em')
            date = date[date.find(' ') + 1:]
            div = p.finds('.t_fsz')
            text = div.ptext
            for x in div.find('.quote'):
                t = ''
                for line in split_lines(x.text):
                    if line.strip():
                        t += '> ' + line
                text = text.replace(x.text, t)
            if lz is None:
                lz = author
            s = text + '\n'
            try:
                rat = p.finds('.ratl').find('tr')
                del rat[0]
                for x in rat:
                    l = [y.text for y in x.find('td')]
                    if l[2].strip():
                        s += l[2] + ' (%s  %s)\n' % (l[0], l[1])
            except:
                pass
            s += author + ' ' + date + '\n---\n'
            if lz == author:
                if flag:
                    self.txts.append(s)
                    flag = False
                else:
                    self.txts[-1] += s
            else:
                self.txts[-1] += s
                flag = True
        self.author = lz

class Nyasama(Yamibo):
    site = 'nyasama'
    formatter_tid = 'http://bbs.nyasama.com/forum.php?mod=viewthread&tid=%s'
    formatter_tid_page = 'http://bbs.nyasama.com/forum.php?mod=viewthread&tid=%s&page=%d'

class Tieba(BaseContent):
    site = 'tieba'
    def fetch(self):
        get = html_getter(cookies[self.site])
        html = get('https://tieba.baidu.com/p/%s' % self.tid)
        self.title = html.finds('.core_title_txt').attrs['title']
        print('Tieba, %s, %s' % (self.title, self.tid))
        pcnt = html.findt('.l_reply_num')
        pcnt = int(pcnt[pcnt.find('共') + 1:-1])
        posts = html.finds('#j_p_postlist').find('.l_post')
        for i in range(2, pcnt + 1):
            posts += get('https://tieba.baidu.com/p/%s?pn=%d' % (self.tid, i)).finds('#j_p_postlist').finds('.l_post')
        self.txts = []
        lz = None
        flag = True
        for p in posts:
            author = p.findt('.d_name')
            text = p.findt('.p_content')
            try:
                date = p.findt(p, '.post-tail-wrap')
                date = date[date.find('楼') + 1:]
            except:
                date = ''
            if lz is None:
                lz = author
            s = text + '\n'
            # grabbing lzl
            try:
                pid = p.finds(p, '.d_post_content').attrs['id']
            except:
                continue
            pid = pid[pid.rfind('_') + 1:]
            pn = 1
            while True:
                l = get('https://tieba.baidu.com/p/comment?tid=%s&pid=%s&pn=%d' % (self.tid, pid, pn)).find('.lzl_cnt')
                if not l:
                    break
                pn += 1
                for x in l:
                    s += x.findt('.lzl_content_main') + '    (%s  %s)\n' % (
                        x.finds('[username]').attrs['username'],
                        x.findt(x, '.lzl_time') )
            s += author
            if date:
                s += ' ' + date
            s += '\n---\n'
            if lz == author:
                if flag:
                    self.txts.append(s)
                    flag = False
                else:
                    self.txts[-1] += s
            else:
                self.txts[-1] += s
                flag = True
        self.author = lz

if __name__ == '__main__':
    from getpass import getuser
    if getuser() == 'karin0':
        for x in ['tieba', 'yamibo', 'nyasama']:
            load_cookies(f'{x}-cookies.json', x)

        get = html_getter(cookies['yamibo'])
        html = get(r'https://bbs.yamibo.com/thread-214724-1-1.html')