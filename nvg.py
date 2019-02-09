import os, json, time, traceback
import zhconv
import requests
from html2text import HTML2Text
from requests_html import HTMLSession, HTML

ver = 11216
cookies = dict()
cache_path = 'cache'
if not os.path.exists(cache_path):
    os.makedirs(cache_path)

def fix_nl(s):
    return s if s.endswith('\n') else (s + '\n')
def process_text(s):
    s = zhconv.convert(fix_nl(s), 'zh-cn')
    lines = (line.strip() for line in s.splitlines())
    return '\n'.join(line for line in lines if line) + '\n'
def optimize_url(url):
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
        self.attrs = elem.attrs
        self.text = elem.text
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

def read_cookies(url): # with EditThisCookie exporting
    ret = dict()
    for x in json.load(open(url, 'r', encoding='utf-8')):
        ret[x['name']] = x['value']
    return ret

class BaseContent(object):
    tid = title = site = author = None
    txts = []

    def fetch(self):
        raise TypeError

    flag = True # whether the last guy is not the author.
    def push_post(self, text, author):
        if author == self.author:
            if self.flag:
                self.txts.append(text)
                self.flag = False
            else:
                self.txts[-1] += text
        else:
            self.txts[-1] += text
            self.flag = True

    def __init__(self, tid):
        self.tid = str(tid)
        if self.site not in cookies:
            cookie_path = self.site + '-cookies.json'
            if os.path.exists(cookie_path):
                load_cookies(cookie_path, self.site)
        if self.site in cookies:
            self.get = html_getter(cookies[self.site])
        else:
            print('Warning: cannot load cookies for', self.site)
            self.get = html_getter({})
        cache_url = cache_path + '/%s_%s.json' % (self.site, self.tid)
        if os.path.exists(cache_url):
            data = json.load(open(cache_url, 'r', encoding='utf-8'))
            self.title = data['title']
            self.author = data['author']
            self.txts = data['txts']
            print(self.site, self.title, self.tid)
            print('Cache found.' if self.txts else 'Failed cache found.')
        else:
            print(self.site, self.tid)
            try:
                self.fetch()
            except Exception:
                self.txts = []
                traceback.print_exc()
                print('Failed.')
            json.dump(
                {'title': self.title, 'txts': self.txts, 'site': self.site, 'tid': self.tid, 'author': self.author}, 
                open(cache_url, 'w', encoding='utf-8'))
    def generate(self, split_mode='none', output_url=None, open_mode='w', if_optimize_url=True, title_level=1):
        print("Generating %s.." % self.title)
        if not self.txts:
            print('Invalid one.')
            return
        txts = [fix_nl(s) for s in self.txts]
        s = ''

        if title_level:
            s = '#' * title_level + self.title + '\n'
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
            output_url = self.title + '.txt'
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
        fp.write(f'Generated by pvg build {ver} of {len(srcs)} posts at {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}\n')
    for x in srcs:
        x.generate(split_mode=split_mode, output_url=output_url, open_mode='a', if_optimize_url=False, title_level=2)

class Yamibo(BaseContent):
    site = 'yamibo'
    formatter_tid = 'https://bbs.yamibo.com/thread-%s-1-1.html'
    formatter_tid_page = 'https://bbs.yamibo.com/thread-%s-%d-1.html'
    def fetch(self):
        html = self.get(self.formatter_tid % self.tid)
        self.title = html.finds('h1.ts').text
        print(f'{self.title}')
        try:
            pcnt = int(html.finds('div.pg > label > span[title]').attrs['title'][1:-1])
        except:
            pcnt = 1

        def parse(doc):
            return list(filter(lambda x: x.attrs['id'][5:].isnumeric(), doc.finds('#postlist').find('div[id^=post]')))

        posts = parse(html)
        for i in range(2, pcnt + 1):
            posts += parse(self.get(self.formatter_tid_page % (self.tid, i)))
            print('Page', i)

        for p in posts:
            div = p.find('.authi')
            author = div[0].text
            date = div[1].findt('em')
            date = date[date.find(' ') + 1:]
            div = p.finds('.t_fsz')
            text = div.ptext
            for quot in div.find('.quote'):
                text = text.replace(quot.text,
                    ''.join([f'> {line}\n' for line in quot.text.splitlines() if line.strip()]) )
            if not self.author:
                self.author = author
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
            self.push_post(s, author)

class Nyasama(Yamibo):
    site = 'nyasama'
    formatter_tid = 'http://bbs.nyasama.com/forum.php?mod=viewthread&tid=%s'
    formatter_tid_page = 'http://bbs.nyasama.com/forum.php?mod=viewthread&tid=%s&page=%d'

class Tieba(BaseContent):
    site = 'tieba'
    def fetch(self):
        html = self.get('https://tieba.baidu.com/p/%s' % self.tid)
        self.title = html.finds('.core_title_txt').attrs['title']
        print('Tieba, %s, %s' % (self.title, self.tid))
        pcnt = html.findt('.l_reply_num')
        pcnt = int(pcnt[pcnt.find('共') + 1:-1])
        posts = html.finds('#j_p_postlist').find('.l_post')
        for i in range(2, pcnt + 1):
            posts += self.get('https://tieba.baidu.com/p/%s?pn=%d' % (self.tid, i)).finds('#j_p_postlist').finds('.l_post')

        for p in posts:
            author = p.findt('.d_name')
            text = p.findt('.p_content')
            try:
                date = p.findt(p, '.post-tail-wrap')
                date = date[date.find('楼') + 1:]
            except:
                date = ''
            if not self.author:
                self.author = author
            s = text + '\n'
            # grabbing lzl
            try:
                pid = p.finds(p, '.d_post_content').attrs['id']
            except:
                continue
            pid = pid[pid.rfind('_') + 1:]
            pn = 1
            while True:
                l = self.get('https://tieba.baidu.com/p/comment?tid=%s&pid=%s&pn=%d' % (self.tid, pid, pn)).find('.lzl_cnt')
                if not l:
                    break
                pn += 1
                for x in l:
                    s += x.findt('.lzl_content_main') + '    (%s  %s)\n' % (
                        x.finds('[username]').attrs['username'],
                        x.findt(x, '.lzl_time') )
            s += author + ((' ' + date) if date else '') + '\n---\n'
            self.push_post(s, author)

if __name__ == '__main__':
    from getpass import getuser
    if getuser() == 'karin0':
        for x in ['tieba', 'yamibo', 'nyasama']:
            load_cookies(f'{x}-cookies.json', x)

        '''
        get = html_getter(cookies['yamibo'])
        html = get(r'https://bbs.yamibo.com/thread-214724-1-1.html')
        '''
