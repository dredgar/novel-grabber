import os
import json
import zhconv
import requests
import time
from requests_html import HTMLSession, HTML

cookies = dict()

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
def process_text(s):
    s = zhconv.convert(fix_nl(s), 'zh-cn')
    lines = []
    t = split_lines(s)
    for r in t:
        if r == '\n' or ('本帖最后由' in r and '编辑' in r):
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
def html_getter(cks):
    se = HTMLSession()
    return lambda url: se.get(url, cookies=cks).html
def html_getter_2(cks):
    return lambda url: HTML(html=requests.get(url, cookies=cks).text)
def ffind(x, s):
    return x.find(s, first=True)

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

class BaseContent(object):
    '''
    Base novel content class.
    tid; site; title; txts
    '''
    tid = ''
    title = ''
    txts = []
    site = ''

    def fetch(self):
        raise RuntimeError('fetch without specific site')
    def __init__(self, tid):
        self.tid = str(tid)
        cache_url = 'cache/%s_%s.json' % (self.site, self.tid)
        if os.path.exists(cache_url):
            data = json.load(open(cache_url, 'r', encoding='utf-8'))
            self.title = data['title']
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
                {'title': self.title, 'txts': self.txts, 'site': self.site, 'tid': self.tid}, 
                open(cache_url, 'w', encoding='utf-8'))
    def generate(self, split_mode='none', output_url=None, open_mode='w', if_optimize_url=True, if_attach_title=False, if_attach_source=True):
        print("Generating %s.." % self.title)
        if not self.txts:
            print('Invalid one.')
            return
        txts = [fix_nl(s) for s in self.txts]
        s = ''
        if if_attach_title:
            s = '## %s\n' % self.title
        if if_attach_source:
            s += 'From %s #%s\n' % (self.site, self.tid)
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

def generate_collection(srcs, output_url, split_mode, if_attach_source=True):
    output_url = optimize_url(output_url)
    if check_refused_overwrite(output_url):
        print('Aborting.')
        return
    with open(output_url, 'w', encoding='utf-8') as fp:
        fp.write(f'Generated at {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}\n')
    for x in srcs:
        x.generate(split_mode=split_mode, output_url=output_url, open_mode='a', if_optimize_url=False, if_attach_title=True, if_attach_source=if_attach_source)

class YamiboNew(BaseContent):
    site = 'yamibo_new'
    def fetch(self):
        se = HTMLSession()
        site = 'https://www.yamibo.com'
        page = se.get(site + '/novel/%s' % self.tid).html
        self.title = page.find('h3.col-md-12')[0].text
        self.txts = [se.get(site + c.find('a[href]')[0].attrs['href']).html.find('#txt')[0].find('.panel-body')[0].text for c in page.find('div[data-key]')]

class Yamibo(BaseContent):
    site = 'yamibo'
    formatter_tid = 'https://bbs.yamibo.com/thread-%s-1-1.html'
    formatter_tid_page = 'https://bbs.yamibo.com/thread-%s-%d-1.html'
    def fetch(self):
        get = html_getter_2(cookies[self.site])
        html = get(self.formatter_tid % self.tid)
        self.title = ffind(html, 'h1.ts').text
        print(f'{self.site}, {self.title}, {self.tid}')
        try:
            pcnt = int(ffind(html, 'div.pg > label > span[title]').attrs['title'][1:-1])
        except:
            pcnt = 1
        posts = list(filter(lambda x: x.attrs['id'][5:].isnumeric(), ffind(html, '#postlist').find('div[id^=post]')))
        for i in range(2, pcnt + 1):
            posts += list(filter(lambda x: x.attrs['id'][5:].isnumeric(), ffind(get(self.formatter_tid_page % (self.tid, i)), '#postlist').find('div[id^=post]')))
            print('Page', i)
        self.txts = []
        lz = None
        flag = True
        for p in posts:
            div = p.find('.authi')
            author = div[0].text
            date = ffind(div[1], 'em').text
            date = date[date.find(' ') + 1:]
            div = ffind(p, '.t_fsz')
            text = div.text
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
                rat = ffind(p, '.ratl').find('tr')
                del rat[0]
                for x in rat:
                    l = [y.text for y in x.find('td')]
                    if l[2].strip():
                        s += l[2] + '    (%s  %s)\n' % (l[0], l[1])
            except:
                pass
            s += author + ' ' + date + '\n'
            if lz == author:
                if flag:
                    self.txts.append(s)
                    flag = False
                else:
                    self.txts[-1] += s
            else:
                self.txts[-1] += s
                flag = True

class Nyasama(Yamibo):
    site = 'nyasama'
    formatter_tid = 'http://bbs.nyasama.com/forum.php?mod=viewthread&tid=%s'
    formatter_tid_page = 'http://bbs.nyasama.com/forum.php?mod=viewthread&tid=%s&page=%d'

class Tieba(BaseContent):
    site = 'tieba'
    def fetch(self):
        get = html_getter(cookies[self.site])
        html = get('https://tieba.baidu.com/p/%s' % self.tid)
        self.title = ffind(html, '.core_title_txt').attrs['title']
        print('Tieba, %s, %s' % (self.title, self.tid))
        pcnt = ffind(html, '.l_reply_num').text
        pcnt = int(pcnt[pcnt.find('共') + 1:-1])
        posts = ffind(html, '#j_p_postlist').find('.l_post')
        for i in range(2, pcnt + 1):
            posts += ffind(ffind(get('https://tieba.baidu.com/p/%s?pn=%d' % (self.tid, i)), '#j_p_postlist'), '.l_post')
        self.txts = []
        lz = None
        flag = True
        for p in posts:
            author = ffind(p, '.d_name').text
            text = ffind(p, '.p_content').text
            try:
                date = ffind(p, '.post-tail-wrap').text
                date = date[date.find('楼') + 1:]
            except:
                date = ''
            if lz is None:
                lz = author
            s = text + '\n'
            # grabbing lzl
            try:
                pid = ffind(p, '.d_post_content').attrs['id']
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
                    s += ffind(x, '.lzl_content_main').text + '    (%s  %s)\n' % (
                        ffind(x, '[username]').attrs['username'],
                        ffind(x, '.lzl_time').text )
            s += author
            if date:
                s += ' ' + date
            s += '\n'
            if lz == author:
                if flag:
                    self.txts.append(s)
                    flag = False
                else:
                    self.txts[-1] += s
            else:
                self.txts[-1] += s
                flag = True
