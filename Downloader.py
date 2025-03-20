import DataBase
import re
import requests
import telegram
from telegram.ext import Updater
import gc
from io import BytesIO


def parse_last(link):
    result = parse_all(link)
    last = result['items'][-1]
    return last


def parse_all(link):
    db = DataBase.DataBase()

    response = requests.get(
        url=link,
    )
    # print(response.text)

    # заголовок
    match = re.search(r'property=\"og:title\" content=\".+?/', response.text)
    anime_title = match[0].split('\"')[-1].split('/')[0]

    # список серий
    items = []
    match = re.search(r'var data = \{\".+?\}', response.text)[0].split('{')[1].replace('}', '')

    for item in match.split(','):
        if item == '' or item == ' ':
            continue
        item = item.split(':')

        name = item[0].replace('\"', '')
        link = item[1].replace('\"', '')
        full_name = anime_title + name

        link720 = 'https://animevost.org/frame5.php?play=' + link + '&old=1' 
        link = 'https://animevost.org/frame5.php?play=' + link + '&old=1' 

        items.append({
            'link': link,
            'link720': link720,
            'title': name,
            'full_title': full_name,
        })

    return {
        'items': items,
        'title': anime_title
    }


class Download:
    def __init__(self, link, updater=None, description=None, users=None, reply_markup=None):
        self.__link = link
        self.__file_id = None
        self.__users = [] if users is None else users
        self.__description = description
        self.__video_file = None
        self.__file_obj = None
        self.__updater = updater
        self.__reply_markup = reply_markup

    def run(self):
        self.get_file_id()
        clear_memory = False
        if self.__file_id is None:
            self.download_file()
            clear_memory = True
        self.send()
        if clear_memory:
            self.__file_obj.flush()
            self.__file_obj.close()
            del self.__file_obj
            gc.collect()

    def download_file(self):
        response = requests.get(
            url=self.__link,
        )
        match = re.search(r'class=\"butt\" download=\".+?href=\".+?\".+?>', response.text)
        video_url = match[0].split('href="')[1].split('"')[0]
        with requests.get(video_url, stream=True) as r:
            r.raise_for_status()
            # self.__file_obj = StringIO()
            self.__file_obj = BytesIO()
            for chunk in r.iter_content(chunk_size=8192):
                self.__file_obj.write(chunk)
            self.__file_obj.seek(0)

    def get_file_id(self):
        db = DataBase.DataBase()
        items = db.get_anime_file_id_by_link(self.__link)
        if len(items) > 0:
            self.__file_id = items[0][0]

    def send(self):
        if self.__updater is None:
            return
        dispatcher = self.__updater.dispatcher
        context = telegram.ext.callbackcontext.CallbackContext(dispatcher)
        for user in self.__users:
            if self.__file_id is None:
                message = context.bot.send_video(
                    chat_id=user, video=self.__file_obj.getbuffer().tobytes(),
                    caption=self.__description,
                    timeout=300,
                    reply_markup=self.__reply_markup
                )
                self.__file_id = message.video.file_id
                db = DataBase.DataBase()
                db.insert_downloaded_anime(self.__link, self.__file_id)
            else:
                message = context.bot.send_video(
                    chat_id=user, video=self.__file_id,
                    caption=self.__description,
                    reply_markup=self.__reply_markup
                )

