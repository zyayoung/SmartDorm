from flask import Flask, request, render_template, redirect
import os
from queue import Queue
import argparse
import string
import PlayListManager
import random
import json
from urllib.request import Request, build_opener, HTTPCookieProcessor, urlopen, quote
import hashlib
import re
import time
import pickle

var_set = json.load(open('config.json'))
play_list_manager = PlayListManager.PlayListManager()

SECRET_KEY = 'BoYanZhhhh'

app = Flask(__name__)

q = Queue()

# log = logging.getLogger('werkzeug')
# log.setLevel(logging.ERROR)


@app.route("/")
def hello():
    return redirect('/music')


@app.route("/add_by_name")
def add_by_name():
    play_list_manager.add_song_by_name_or_link(request.args.get('name'))
    return 'OK'


@app.route('/music/list')
def music_list():
    re = ''
    for obj in play_list_manager.db.objects:
        re += '{}<br/>'.format(obj)
    return re


@app.route('/music/del')
def music_del():
    if request.args.get('id') is not None:
        song_id = request.args.get('id')
        play_list_manager.del_song_by_id_or_av(song_id)
    return redirect('/music')


@app.route('/music/player')
def music_player():
    return render_template('player.html', src=var_set['http_src'])


@app.route('/music/remove_from_playlist')
def remove_from_playlist():
    if request.args.get('id') is not None and request.args.get('order') is not None:
        song_id = request.args.get('id')
        order = int(request.args.get('order'))
        if str(play_list_manager.q_new_song[order]['song_id']) == song_id:
            play_list_manager.q_new_song.pop(order)
    return redirect('/music')


@app.route('/music/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            return 'No file part'
        for idx, file in enumerate(request.files.getlist('file')):
            song_id = random.randint(1000000, 9999999)
            filename = 'up{}.mp3'.format(song_id)
            while os.path.exists(os.path.join(var_set['download_path'], 'song', filename)):
                song_id = random.randint(1000000, 9999999)
                filename = 'up{}.mp3'.format(song_id)
            file.save(os.path.join(var_set['download_path'], 'song', filename))
            play_list_manager.add_song_by_filename(
                filename,
                song_id=song_id,
                al=request.form.get('al{}'.format(idx)),
                ar=request.form.get('ar{}'.format(idx)),
                song_name=request.form.get('name{}'.format(idx)),
            )
        return redirect('/music')
    return render_template('upload.html')


@app.route('/music')
def music():
    if request.args.get('offset') is not None:
        offset = float(request.args.get('offset'))
        play_list_manager.set_offset_by_ratio(offset, wait=True)
        return redirect('/music')
    if request.args.get('id') is not None:
        song_id = request.args.get('id')
        if song_id.startswith('av'):
            play_list_manager.add_song_by_av(int(song_id[2:]))
        elif song_id.startswith('up'):
            play_list_manager.add_song_by_filename(song_id)
        else:
            play_list_manager.add_song_by_id(int(song_id))
        return redirect('/music')
    elif request.args.get('command') is not None:
        command = request.args.get('command')
        if command == 'next':
            play_list_manager.next()
        elif command == 'start':
            play_list_manager.pause = False
        elif command == 'pause':
            play_list_manager.pause = True
        elif command == 'vup':
            play_list_manager.vup()
        elif command == 'vdown':
            play_list_manager.vdown()
        return redirect('/music')
    return render_template(
        'music.html',
        now=play_list_manager.now_playing,
        paused=play_list_manager.pause,
        volume=play_list_manager.volume,
        data_list=play_list_manager.db.objects,
        play_list=play_list_manager.q_new_song,
    )


@app.route('/ele')
def ele():
    cookies = HTTPCookieProcessor()
    opener = build_opener(cookies)
    req = Request(
        url=r'http://202.120.1.29:8080/AppQuery/AppInterface.asmx',
        headers={
            'Content-Type': 'text/xml; charset=utf-8'
        },
        data=(
            """<?xml version="1.0" encoding="utf-8"?>
            <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
              <soap12:Body>
                <GetDayHardRecordInfo_New xmlns="http://tempuri.org/">
                  <PhoneSignKey>"""+var_set['PhoneSignKey']+"""</PhoneSignKey>
                  <RoomDm>"""+var_set['RoomDm']+"""</RoomDm>
                  <Mdid>"""+var_set['Mdid']+"""</Mdid>
                </GetDayHardRecordInfo_New>
              </soap12:Body>
            </soap12:Envelope>
            """
        ).encode()
    )

    m = re.search(
        r"<GetDayHardRecordInfo_NewResult>(.+?)</GetDayHardRecordInfo_NewResult>",
        opener.open(req).read().decode()
    )
    data = []
    for d in json.loads(m.group(1))['data']:
        t = time.mktime(time.strptime(d['hdsavetime'], '%Y/%m/%d %H:%M:%S'))
        # day -= 1
        if time.localtime(t).tm_hour < 6:
            t -= time.localtime(t).tm_hour * 3600 + time.localtime(t).tm_min * 60 + time.localtime(t).tm_sec + 1

        # we only show 4 month
        if time.time() - t < 3600 * 24 * 30 * 4:
            data.append([t, d['used']])
    return render_template('ele.html', data=data)


def _trans(q):
    appid = var_set['appid']  # 你的appid
    secretKey = var_set['secretKey']  # 你的密钥
    if not q:
        return ''
    myurl = 'http://api.fanyi.baidu.com/api/trans/vip/translate'
    fromLang = 'en'
    toLang = 'zh'
    salt = random.randint(32768, 65536)

    sign = appid+q+str(salt)+secretKey
    m_MD5 = hashlib.md5(sign.encode('utf-8'))
    sign = m_MD5.hexdigest()
    myurl = myurl+'?appid='+appid+'&q=' + \
        quote(q)+'&from='+fromLang+'&to='+toLang + \
        '&salt='+str(salt)+'&sign='+sign
    try:
        response = urlopen(myurl).read().decode()
    except KeyError as e:
        return '{} {}'.format(e, 'Network Error')
    try:
        return json.loads(response)['trans_result'][0]['dst']
    except KeyError as e:
        return '{} {}'.format(e, response)


cache = {}
trans_history = []


@app.route('/trans', methods=['GET', 'POST'])
def trans():
    if request.args.get('id'):
        return render_template('trans_result.html', out=cache[trans_history[int(request.args.get('id'))]['full_key']])
    if request.method == 'POST':
        __to_trans = request.form.get('en')
        if __to_trans in cache:
            out = cache[__to_trans]
        else:
            __to_trans = re.sub(r'\r?\n\d+\r?\n', '\r\n', __to_trans)
            # print([__to_trans])
            to_trans = []

            for _to_trans in re.split(r'\.\r?\n', __to_trans):
                _to_trans = _to_trans.replace('\n', ' ').replace('\r', '')
                if _to_trans and not _to_trans.endswith('.'):
                    _to_trans = _to_trans + '.'
                while _to_trans:
                    cut_at = _to_trans[4000:].find('.') + 4000
                    to_trans.append(_to_trans[:cut_at + 1])
                    _to_trans = _to_trans[cut_at + 2:]
            out = []
            for line in to_trans:
                out.append(_trans(line))
            cache[request.form.get('en')] = out
            trans_history.append({
                'title': ' '.join(request.form.get('en').split()[:10]) + (' ...' if request.form.get('en').split()[10:] else ''),
                'full_key': request.form.get('en'),
            })
            f = open('data.pkl', 'w')
            pickle.dump((cache, trans_history), f)
            f.close()
        return render_template('trans_result.html', out=out)
    else:
        return render_template('trans_form.html', history=trans_history)


@app.route('/srcnn')
def srcnn():
    return render_template('srcnn.html')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Music Chooser Server.')
    parser.add_argument('-ip', default='0.0.0.0', type=str)
    parser.add_argument('-port', default='5001', type=str)
    parser.add_argument('-sk', default='BoYanZhhhh', type=str)
    args = vars(parser.parse_args())
    SECRET_KEY = args['sk']
    if SECRET_KEY == 'YourSecretKey':
        SECRET_KEY = ''.join(
            random.sample(string.ascii_letters + string.digits, 8))
    print('start')
    app.run(host=args['ip'], port=args['port'])
