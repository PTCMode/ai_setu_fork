import os
from os.path import dirname, join, exists
import ahocorasick
import yaml
try:
    import hjson as json
except:
    import json


curpath = dirname(__file__) #当前路径
save_image_path= join(curpath,'SaveImage')  # 保存图片路径

font_path = join(curpath,"./resources/font/093.ttf")  #字体文件路径

config_path = join(curpath,"config.yaml")
if not exists(save_image_path):
    os.mkdir(save_image_path) #创建img保存目录

temp_image_path= join(curpath,'TempImage')  # 保存临时图片路径
if not exists(temp_image_path):
    os.mkdir(temp_image_path) #创建临时img保存目录

tag_path = join(curpath,"./resources/magicbooks/tag_data.json")
with open((tag_path),encoding="utf-8") as f: #初始化tags
    tag_data = json.load(f)

with open(config_path,encoding="utf-8") as f: #初始化配置文件
    config = yaml.safe_load(f)#读取配置文件


with open(join(curpath, './resources/magicbooks/magic.json'),encoding="utf-8") as f: #初始化法典
    magic_data = json.load(f)
with open(join(curpath, './resources/magicbooks/magic_pure.json'),encoding="utf-8") as f: #初始化法典(纯净版)
    magic_data_pure = json.load(f)
magic_data_title = []
for i in magic_data:
    magic_data_title.append(i) #初始化法典目录

with open(join(curpath, './resources/magicbooks/magic_dark.json'),encoding="utf-8") as f: #初始化法典(黑暗版)
    magic_data_dark = json.load(f)
magic_data_dark_title = []
for i in magic_data_dark:
    magic_data_dark_title.append(i) #初始化黑暗法典目录


ip_token_list = [(i, j) for i in config['api_ip'] for j in config['token'] if i != j] #初始化ip和token的列表(轮询池)


actree = ahocorasick.Automaton()#初始化AC自动机
for index, word in enumerate(config['wordlist']):
    actree.add_word(word, (index, word))
actree.make_automaton() #初始化完成，一般来说重启才能重载屏蔽词

actree_r18 = ahocorasick.Automaton()#初始化AC自动机
for index, word in enumerate(config['r18_wordlist']):
    actree_r18.add_word(word, (index, word))
actree_r18.make_automaton() #初始化完成，一般来说重启才能重载屏蔽词

async def try_delete_msg(bot, ev, message_id):
    try:
        if config['delete_massege']:    await bot.delete_msg(message_id = message_id) #撤回反馈互动,防止刷屏
    except:
        if config['ask_4_admin_priv']:  await bot.send(ev, f"Bot撤回消息失败, 请赋予Bot管理员")


def check_nsfw_conf(group_id):
    error_msg = ""
    if not group_id in config['r18_group_enable']:
        error_msg = f"配置中该群未开启R18"
    return error_msg