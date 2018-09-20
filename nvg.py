import os
import json
import zhconv
import requests
from requests_html import HTMLSession, HTML

def fix_nl(s):
    '''
    If s ends with \\n, return itself, or return it with an appending \\n.
    '''
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
    return os.path.exists(url) and ask_with_n('%s exists. Overwrite?' % url)

def read_cookies(url):
    '''
    Read cookies formatted for requests module from a file that EditThisCookie extension exports to.
    :param url: Path to the file EditThisCookie exported to.
    '''
    ret = dict()
    for x in json.load(open(url, 'r', encoding='utf-8')):
        ret[x['name']] = x['value']
    return ret
def check_cookies(cks):
    if cks is None:
        raise ValueError('cookies not loaded')
def html_getter(cks):
    se = HTMLSession()
    return lambda url: se.get(url, cookies=cks).html
def html_getter_2(cks):
    return lambda url: HTML(html=requests.get(url, cookies=cks).text)
def verified_return(func):
    def wrapper(**kwargs):
        a = func(**kwargs)
        b = func(**kwargs)
        if a == b:
            return a
        return wrapper(**kwargs)
    return wrapper

class BaseContent(object):
    '''
    Base novel content class.
    tid; site; title; txts; success
    '''
    tid = ''
    title = ''
    txts = []
    success = False
    site = ''

    def __init__(self, tid):
        self.tid = str(tid)
        cache_url = 'cache/%s_%s.json' % (self.site, self.tid)
        if os.path.exists(cache_url):
            data = json.load(open(cache_url, 'r', encoding='utf-8'))
            self.title = data['title']
            self.txts = data['txts']
            self.success = data['success'] if 'success' in data else True
            print(self.site, self.title, self.tid)
            print('Cache found.' if self.success else 'Failed cache found.')
        else:
            while not self.success:
                try:
                    self.fetch()
                    self.success = True
                except:
                    if not ask_with_y('Failed. Retry?'):
                        if not ask_with_n('Save failed cache?'):
                            return
                        break
            json.dump(
                {'title': self.title, 'txts': self.txts, 'site': self.site, 'tid': self.tid, 'success': self.success}, 
                open(cache_url, 'w', encoding='utf-8'))

def generate(src, split_mode='none', output_url=None, open_mode='w', if_optimize_url=True, if_attach_title=False, if_attach_source=False):
    ''' if src is None:
        ret = json.load(open('ret.json', 'r', encoding='utf-8'))
    else:
        json.dump(ret, open('ret.json', 'w', encoding='utf-8')) '''
    print("Generating %s.." % src.title)
    if not src.success:
        print('Not success one.')
        return
    txts = [fix_nl(s) for s in src.txts]
    s = ''
    if if_attach_title:
        s = '## %s\n' % src.title
    if if_attach_source:
        s += 'From %s #%s\n' % (src.site, src.tid)
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
    
    if output_url is None:
        output_url = '%s.txt' % src.title
    if if_optimize_url:
        output_url = optimize_url(output_url)
    if open_mode.startswith('w') and check_refused_overwrite(output_url):
        print('Aborting.')
        return
    with open(output_url, open_mode, encoding='utf-8') as f:
        f.write(process_text(s))

def generate_collection(srcs, output_url, split_mode, if_attach_source=True):
    output_url = optimize_url(output_url)
    if check_refused_overwrite(output_url):
        print('Aborting.')
        return
    if os.path.exists(output_url):
        os.remove(output_url)
    for x in srcs:
        generate(x, split_mode=split_mode, output_url=output_url, open_mode='a', if_optimize_url=False, if_attach_title=True, if_attach_source=if_attach_source)

yamibo_cookies = None
tieba_cookies = None

def load_yamibo_cookies(url):
    global yamibo_cookies
    yamibo_cookies = read_cookies(url)

def load_tieba_cookies(url):
    global tieba_cookies
    tieba_cookies = read_cookies(url)

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
    def fetch(self):
        check_cookies(yamibo_cookies)
        get = html_getter_2(yamibo_cookies)
        html = get('https://bbs.yamibo.com/thread-%s-1-1.html' % self.tid)
        self.title = html.find('h1.ts', first=True).text
        print('Yamibo, %s, %s' % (self.title, self.tid))
        try:
            pcnt = int(html.find('div.pg > label > span[title]', first=True).attrs['title'][1:-1])
        except:
            pcnt = 1
        posts = list(filter(lambda x: x.attrs['id'][5:].isnumeric(), html.find('#postlist', first=True).find('div[id^=post]')))
        for i in range(2, pcnt + 1):
            posts += list(filter(lambda x: x.attrs['id'][5:].isnumeric(), get('https://bbs.yamibo.com/thread-%s-%d-1.html' % (self.tid, i)).find('#postlist', first=True).find('div[id^=post]')))
            print('Page', i)
        self.txts = []
        lz = None
        flag = True
        for p in posts:
            div = p.find('.authi')
            author = div[0].text
            date = div[1].find('em', first=True).text
            date = date[date.find(' ') + 1:]
            div = p.find('.t_fsz', first=True)
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
                rat = p.find('.ratl', first=True).find('tr')
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

class Tieba(BaseContent):
    site = 'tieba'
    def fetch(self):
        check_cookies(tieba_cookies)
        get = html_getter(tieba_cookies)
        html = get('https://tieba.baidu.com/p/%s' % self.tid)
        self.title = html.find('.core_title_txt', first=True).attrs['title']
        print('Tieba, %s, %s' % (self.title, self.tid))
        pcnt = html.find('.l_reply_num', first=True).text
        pcnt = int(pcnt[pcnt.find('共') + 1:-1])
        posts = html.find('#j_p_postlist', first=True).find('.l_post')
        for i in range(2, pcnt + 1):
            posts += get('https://tieba.baidu.com/p/%s?pn=%d' % (self.tid, i)).find('#j_p_postlist', first=True).find('.l_post')
        self.txts = []
        lz = None
        flag = True
        for p in posts:
            author = p.find('.d_name', first=True).text
            text = p.find('.p_content', first=True).text
            try:
                date = p.find('.post-tail-wrap', first=True).text
                date = date[date.find('楼') + 1:]
            except:
                date = ''
            if lz is None:
                lz = author
            s = text + '\n'
            # grabbing lzl
            try:
                pid = p.find('.d_post_content', first=True).attrs['id']
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
                    s += x.find('.lzl_content_main', first=True).text + '    (%s  %s)\n' % (
                        x.find('[username]', first=True).attrs['username'],
                        x.find('.lzl_time', first=True).text )
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
