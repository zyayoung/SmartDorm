# coding = utf-8
import os
import time
import signal
import re
import threading as td
from queue import Queue
import random
from urllib.request import urlopen, urlretrieve, Request
from urllib.parse import urlencode
import json
import subprocess
import glob
import signal

var_set = json.load(open('config.json'))
HEAD = {'User-Agent': 'BiLiBiLi Audio Streamer/1.0.0 (1328410180@qq.com)', "Cookie": "buvid3=91585DCB-8DE6-4C63-9173-45C98A2A511C77387infoc; LIVE_BUVID=AUTO5015502255888665"}


class JsonDB:
    def __init__(self):
        if not os.path.exists("db.json"):
            f = open("db.json", "w")
            json.dump([], f)
            f.close()
            self.objects = []
        else:
            f = open("db.json", 'r')
            self.objects = json.load(f)
            f.close()

    def save(self):
        f = open("db.json", "w")
        json.dump(self.objects, f)
        f.close()

    def append(self, obj):
        self.objects.append(obj)

    def delete(self, obj):
        return self.objects.remove(obj)

    def get_object_by_key(self, key, value):
        for obj in self.objects:
            if str(obj[key]) == str(value):
                return obj


class PlayListManager:
    def __init__(self):
        print('Initializing play list...')
        self.play_list_ids = []
        self.file_names = []
        self.q_new_song = Queue()
        self.play_next = False
        self.pause = False
        self.offset = None
        self.volume = 0
        self.db = JsonDB()
        self.now_adding = []
        self.now_playing = {}
        try:
            self.ffserver = subprocess.Popen(
                        ["ffserver", "-f", var_set['ffserver_config']],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True
                    )
        except FileNotFoundError:
            print("ffserver not found!")

        self.song_path = os.path.join(var_set['download_path'], 'song')
        # load local playlist
        if not os.path.exists(var_set['download_path']):
            os.mkdir(var_set['download_path'])
            os.mkdir(self.song_path)
        self.player = td.Thread(target=self._player, name='Player')
        self.player.start()

    def vup(self):
        self.volume += 5

    def vdown(self):
        self.volume -= 5

    def next(self, wait=True):
        old_time = self.now_playing['addtime'] if 'addtime' in self.now_playing else 0
        self.play_next = True
        if wait:
            # wait
            while self.play_next or 'addtime' not in self.now_playing or self.now_playing['addtime'] == old_time:
                time.sleep(0.01)
        self.now_playing['time'] = 0
        return

    def add_song_by_name_or_link(self, name):
        if not name:
            return
        print('Searching', name)
        try:
            song_id = re.search(r'https?://music\.163\.com/song/(\d+)/', name)
            if song_id:
                self.add_song_by_id(int(song_id.group(1)))
                return
            song_id = re.search(r'https?://music\.163\.com/m/song\?id=(\d+)', name)
            if song_id:
                self.add_song_by_id(int(song_id.group(1)))
                return

            song_id = re.search(r'https?://www.bilibili.com/video/av(\d+)', name)
            if song_id:
                self.add_song_by_av(int(song_id.group(1)))
                return

            song_id = re.search(r'^av(\d+)$', name)
            if song_id:
                self.add_song_by_av(int(song_id.group(1)))
                return

            api_url = 'https://api.imjad.cn/cloudmusic/?'
            code = urlencode({'type': 'search', 'limit': 1, 's': name})
            code = json.loads(urlopen(api_url + code).read().decode('utf-8'))
            if code['code'] == 200:
                song_id = code['result']['songs'][0]['id']
                self.add_song_by_id(song_id)
        except Exception as e:  # 防炸
            print('shit')
            print(e)

    def add_song_by_av(self, aid):
        print('Adding', aid)
        try:
            song_id = int(aid)
            if song_id in self.now_adding:
                return
            self.now_adding.append(song_id)
            # check id
            old_obj = self.db.get_object_by_key('song_id', 'av{}'.format(song_id))
            if old_obj:
                self.q_new_song.put(old_obj)
                self.next()
                self.now_adding.remove(song_id)
                return

            # get song url
            req = Request('http://api.imjad.cn/bilibili/v2/?aid=' + str(song_id) + '&type=archieve', headers=HEAD)
            info = json.loads(
                urlopen(req).read().decode('utf-8')
            )
            if info['code'] != 0:
                print('[error]')
                print(info)
                return

            song_name = info['data']['title']
            song_tname = info['data']['tname']
            song_uploader = info['data']['owner']['name']


            # download song
            mp3_file_name = 'av%012d' % song_id + '.mp3'

            print('Downloading...')
            print('songName: ' + song_name)
            print('songUploader: ' + song_uploader)
            req = Request('http://api.bilibili.com/playurl?callback=callbackfunction&aid={}&page=1&platform=html5&quality=1'.format(song_id), headers=HEAD)
            song_url = json.loads(
                urlopen(req).read().decode('utf-8')
            )['durl'][0]['url']
            print('songUrl: ' + song_url)
            req = Request(song_url, headers=HEAD)
            if os.path.exists(os.path.join(self.song_path, mp3_file_name)):
                os.remove(os.path.join(self.song_path, mp3_file_name))
            savep = subprocess.Popen(
                ["ffmpeg", "-i", "pipe:0", os.path.join(self.song_path, mp3_file_name)],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
            )
            tmp_file = urlopen(req)
            while True:
                buf = tmp_file.read(1024)
                savep.stdin.write(buf)
                savep.stdin.flush()
                if len(buf) < 1024 or buf[-1] == b'\0':
                    break

            savep.stdin.write(b'\0')
            savep.stdin.flush()
            time.sleep(1)
            savep.send_signal(signal.SIGINT)
            print("downloaded")
            try:
                savep.wait(timeout=1)
            except subprocess.TimeoutExpired:
                savep.terminate()
                pass
            savep.kill()
            new_song_obj = {
                'mp3_file_name': mp3_file_name,
                'song_url': song_url,
                'song_name': song_name,
                'song_id': 'av{}'.format(song_id),
                'states': 'downloaded',
                'ar': song_uploader,
                'al': song_tname,
                'detail': info,
                'ori': "https://www.bilibili.com/video/av{}".format(song_id),
            }
            self.db.append(new_song_obj)
            self.db.save()

            # push q_new_song
            self.q_new_song.put(new_song_obj)
            self.next()
            self.now_adding.remove(song_id)
        except Exception as e:  # 防炸
            print('shit')
            print(e)

    def add_song_by_id(self, song_id):
        print('Adding', song_id)
        try:
            song_id = int(song_id)
            if song_id in self.now_adding:
                return
            self.now_adding.append(song_id)
            # check id
            old_obj = self.db.get_object_by_key('song_id', song_id)
            if old_obj:
                self.q_new_song.put(old_obj)
                self.next()
                self.now_adding.remove(song_id)
                return

            # get song url
            info = json.loads(
                urlopen('https://api.imjad.cn/cloudmusic/?id=' + str(song_id) + '&br=320000').read().decode('utf-8')
            )
            if info['code'] != 200:
                print('[error]')
                print(info)
                return
            song_url = info['data'][0]['url']
            detail_info = json.loads(
                urlopen('https://api.imjad.cn/cloudmusic/?type=detail&id=' + str(song_id)).read().decode('utf-8')
            )
            if detail_info['code'] != 200:
                print('[error]')
                print(detail_info)
                return
            song_name = detail_info['songs'][0]['name']

            # download song
            mp3_file_name = '%012d' % song_id + '.mp3'

            print('Downloading...')
            print('songName: ' + song_name)
            print('songUrl: ' + song_url)
            urlretrieve(song_url, os.path.join(self.song_path, mp3_file_name))
            new_song_obj = {
                'mp3_file_name': mp3_file_name,
                'song_url': song_url,
                'song_name': song_name,
                'song_id': song_id,
                'states': 'downloaded',
                'ar': ' '.join([ar['name'] for ar in detail_info['songs'][0]['ar']]),
                'al': detail_info['songs'][0]['al']['name'],
                'detail': detail_info,
                'ori': "http://music.163.com/song?id={}".format(song_id),
            }
            self.db.append(new_song_obj)
            self.db.save()

            # push q_new_song
            self.q_new_song.put(new_song_obj)
            self.next()
            self.now_adding.remove(song_id)
        except Exception as e:  # 防炸
            print('shit')
            print(e)

    def del_song_by_id_or_av(self, song_id):
        # del song files
        try:
            obj = self.db.get_object_by_key('song_id', song_id)
            song_path = os.path.join(var_set['download_path'], 'song')
            mp3_file_path = os.path.join(song_path, obj['mp3_file_name'])
            if os.path.exists(mp3_file_path):
                os.remove(mp3_file_path)
            self.db.delete(obj)
            self.db.save()
            print('Deleted')
        except Exception as e:  # 防炸
            print('shit')
            print(e)

    def set_offset_by_ratio(self, ratio, wait=False):
        if 'tottime' in self.now_playing:
            self.offset = int(self.now_playing['tottime'] * ratio)
        while self.offset and wait:
            time.sleep(0.01)

    def set_offset(self, offset, wait=False):
        self.offset = offset
        while self.offset and wait:
            time.sleep(0.01)

    def _player(self):
        while True:
            while not self.db.objects:
                time.sleep(0.1)

            # get next song
            if not self.q_new_song.empty():
                nxt_song = self.q_new_song.get()
            else:
                nxt_song = random.choice(self.db.objects)
            self.now_playing = nxt_song
            self.now_playing['time'] = 0
            song_path = os.path.join(var_set['download_path'], 'song')
            mp3_file_path = os.path.join(song_path, nxt_song['mp3_file_name'])
            p = subprocess.Popen(
                ["ffmpeg", "-i", mp3_file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            while p.poll() is None:
                p_time = re.search(r'Duration: (\d+):(\d+):(\d+).(\d+),', p.stdout.readline())
                if p_time:
                    self.now_playing['tottime'] = int(p_time.group(1)) * 3600 + int(p_time.group(2)) * 60 + int(p_time.group(3))
                    break
            p.kill()
            p.wait()
            p = subprocess.Popen(
                ["ffmpeg", "-re", "-i", mp3_file_path, "-filter:a", "loudnorm", "-af", "volume={}dB".format(self.volume), "http://127.0.0.1:8090/feed1.ffm"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            p_start_time = time.time()
            t = 0
            self.now_playing['time'] = t + int(time.time() - p_start_time)
            self.now_playing['addtime'] = time.clock()
            while p.poll() is None:
                self.now_playing['time'] = t + int(time.time() - p_start_time)
                time.sleep(0.1)
                # Pause
                if self.pause:
                    t += int(time.time() - p_start_time)
                    p.send_signal(2)
                    try:
                        p.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        p.terminate()
                    p.kill()
                    silent = subprocess.Popen(
                        ["ffmpeg", "-re", "-f", "lavfi", "-i", "aevalsrc=0", "http://127.0.0.1:8090/feed1.ffm"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True
                    )
                    print("Paused, will start at", t)
                    while self.pause:
                        time.sleep(0.01)
                    silent.send_signal(2)
                    silent.kill()
                    self.set_offset(t)

                # Offset
                if self.offset:
                    t = self.offset
                    if p.poll() is None:
                        p.send_signal(2)
                        try:
                            p.wait(timeout=1)
                        except subprocess.TimeoutExpired:
                            p.terminate()
                        p.kill()
                    print("Starting at", self.offset)
                    p_start_time = time.time()
                    p = subprocess.Popen(
                        ["ffmpeg", "-ss", str(self.offset), "-re", "-i", mp3_file_path, "-filter:a", "loudnorm", "-af", "volume={}dB".format(self.volume), "http://127.0.0.1:8090/feed1.ffm"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True
                    )
                    self.offset = None

                # Next
                if self.play_next:
                    p.send_signal(2)
                    try:
                        p.wait(timeout=1)
                        self.play_next = False
                        break
                    except subprocess.TimeoutExpired:
                        p.terminate()
                        self.play_next = False
                        break

                # Force stop
                if self.now_playing['tottime'] - self.now_playing['time'] < 0:
                    p.send_signal(2)
                    try:
                        p.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        p.terminate()
                        break
            # print('FFmpeg Ended with code', p.poll())
            p.kill()
