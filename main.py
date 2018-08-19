#!/usr/bin/python
from requests_html import HTMLSession, HTML
import requests
import zhconv
import os
import json

def fix_nl(s):
    if not s:
        return '\n'
    return (s + '\n') if s[-1] != '\n' else s
def read_cookies(fn):
    ret = dict()
    with open(fn, 'r') as fp:
        for x in json.load(fp):
            ret[x['name']] = x['value']
    return ret
def html_getter(cks):
    se = HTMLSession()
    return lambda url: se.get(url, cookies=cks).html
def html_getter_2(cks):
    return lambda url: HTML(html=requests.get(url, cookies=cks).text)
def check_twice(grabber):
    def wrapper(tid):
        a = grabber(tid)
        b = grabber(tid)
        if a == b:
            return a
        return wrapper(tid)
    return wrapper
@check_twice
def yamibo_new(nid):
    se = HTMLSession()
    site = 'https://www.yamibo.com'
    page = se.get(site + '/novel/%d' % nid).html
    title = page.find('h3.col-md-12')[0].text
    txts = [se.get(site + c.find('a[href]')[0].attrs['href']).html.find('#txt')[0].find('.panel-body')[0].text for c in page.find('div[data-key]')]
    return txts, title
@check_twice
def yamibo(tid):
    get = html_getter_2(read_cookies('yamibo-cookies.json'))
    html = get('https://bbs.yamibo.com/thread-%s-1-1.html' % tid)
    title = html.find('h1.ts', first=True).text
    print('Yamibo, %s, %s' % (title, tid))
    try:
        pcnt = int(html.find('div.pg > label > span[title]', first=True).attrs['title'][1:-1])
    except:
        pcnt = 1
    posts = list(filter(lambda x: x.attrs['id'][5:].isnumeric(), html.find('#postlist', first=True).find('div[id^=post]')))
    for i in range(2, pcnt + 1):
        posts += list(filter(lambda x: x.attrs['id'][5:].isnumeric(), get('https://bbs.yamibo.com/thread-%s-%d-1.html' % (tid, i)).find('#postlist', first=True).find('div[id^=post]')))
    txts = []
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
                txts.append(s)
                flag = False
            else:
                txts[-1] += s
        else:
            txts[-1] += s
            flag = True
    return txts, title
    # return posts
@check_twice
def tieba(tid):
    get = html_getter(read_cookies('tieba-cookies.json'))
    html = get('https://tieba.baidu.com/p/%s' % tid)
    title = html.find('.core_title_txt', first=True).attrs['title']
    print('Tieba, %s, %s' % (title, tid))
    pcnt = html.find('.l_reply_num', first=True).text
    pcnt = int(pcnt[pcnt.find('共') + 1:-1])
    posts = html.find('#j_p_postlist', first=True).find('.l_post')
    for i in range(2, pcnt + 1):
        posts += get('https://tieba.baidu.com/p/%s?pn=%d' % (tid, i)).find('#j_p_postlist', first=True).find('.l_post')
    txts = []
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
            l = get('https://tieba.baidu.com/p/comment?tid=%s&pid=%s&pn=%d' % (tid, pid, pn)).find('.lzl_cnt')
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
                txts.append(s)
                flag = False
            else:
                txts[-1] += s
        else:
            txts[-1] += s
            flag = True
    return txts, title
    # return posts
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
def generate(ret, split_mode='none', add_title=False, char_title='第 %d 章', output_url=None, open_mode='w'):
    txts, title = ret
    print("Generating %s.." % title)
    txts = [fix_nl(s) for s in txts]
    s = ''
    if add_title:
        s = '## %s\n' % title
    if split_mode == 'none':
        s += '\n'.join(txts) + '\n'
    elif split_mode == 'symbol':
        s += '\n$$$$$$$$$$$$\n\n'.join(txts) + '\n'
    elif split_mode == 'first_line':
        s += '\n'.join(['### ' + txt for txt in txts]) + '\n'
    else:
        raise ValueError
    
    if output_url is None:
        output_url = '%s.txt' % title
    output_url = output_url.replace('*', '')
    for x in ('/', '?', ':', '|', '\\', '<', '>'):
        output_url = output_url.replace(x, ' ')
    if open_mode == 'w':
        while os.path.exists(output_url):
            if input('%s exists. Overwrite? (n) ' % output_url).lower() == 'y':
                break
            output_url = input('New output url: ')
    with open(output_url, open_mode) as f:
        f.write(process_text(s))

def generate_combine(rets, output_url):
    for x in rets:
        generate(x, add_title=True, output_url=output_url, open_mode='a')

''''
if __name__ == '__main__':
    generate_combine([
        tieba(2178441316),
        yamibo(104392),
            ], 'test.txt')
    generate(yamibo(206626), 'symbol')
'''

