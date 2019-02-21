from flask import Flask, flash, request, render_template, redirect
from werkzeug.utils import secure_filename
import os
from queue import Queue
import argparse
import random
import string
import PlayListManager
import json

var_set = json.load(open('config.json'))
play_list_manager = PlayListManager.PlayListManager()

SECRET_KEY = 'BoYanZhhhh'

app = Flask(__name__)

q = Queue()

# log = logging.getLogger('werkzeug')
# log.setLevel(logging.ERROR)


@app.route("/")
def hello():
    return render_template('index.html')


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


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ['mp3']


@app.route('/music/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            return 'No file part'
        file = request.files['file']
        # if user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            return 'No selected file'
        if file and allowed_file(file.filename):
            filename = 'up{}'.format(random.randint(100000000, 999999999)+'.mp3')
            while os.path.exists(os.path.join(var_set['download_path'], 'song', filename)):
                filename = 'up{}'.format(random.randint(100000000, 999999999)+'.mp3')
            file.save(os.path.join(var_set['download_path'], 'song', filename))
            play_list_manager.add_song_by_filename(
                filename,
                al=request.args.get('al'),
                ar=request.args.get('ar'),
                song_name=request.args.get('name'),
            )
            return redirect('/music')
        else:
            return "File type not allowed!"
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
        if song_id.startswith('up'):
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
    re = '<p><a href="?command=start">start</a>&nbsp; \
             <a href="?command=pause">pause</a>&nbsp; \
             <a href="?command=next">next</a>&nbsp; \
             <a href="?command=vup">vup</a>&nbsp; \
             <a href="?command=vdown">vdown</a></p>'
    for obj in play_list_manager.db.objects:
        re += '<p>{id}.<a href="?id={id}">{name}</a></p>\n'.format(
            id=obj['song_id'],
            name=obj['song_name']
        )
    return render_template(
        'music.html',
        now=play_list_manager.now_playing,
        paused=play_list_manager.pause,
        volume=play_list_manager.volume,
        data_list=play_list_manager.db.objects
    )


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
