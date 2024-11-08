import random
from hoshino import Service, priv
from . import until
from .util import tag_data, config, check_nsfw_conf
import time

date = True

sv_help = '''
今天我是什么少女
'''.strip()

sv = Service(
    name = '今天也是少女',  #功能名
    use_priv = priv.NORMAL, #使用权限
    manage_priv = priv.ADMIN, #管理权限
    visible = True, #False隐藏
    enable_on_default = True, #是否默认启用
    bundle = '通用', #属于哪一类
    help_ = sv_help #帮助文本
    )


tags_id = ["类型","身份","头发","发色","衣服","鞋子","装饰","胸","表情","二次元","基础动作","场景","物品","天气","环境"]
tags = "{{highly detailed}},{{masterpiece}},{ultra-detailed},{illustration},{{1girl}},{{best quality}}" #正面默认tags
ntags = "lowres,bad anatomy,bad hands,text,error,missing fingers,extra digit,fewer digits,cropped,worst quality,low quality,normal quality,jpeg artifacts,signature,watermark,username,blurry,missing arms,long neck,Humpbacked" #负面默认tags


async def be_girl(uid):
    tags = "1girl,solo"
    goal_tag = {}
    uid = int(uid)
    random.seed(uid * int((time.time() + time.localtime().tm_gmtoff) / 3600 / 24))
    for i in tags_id:
        tag_list = []
        for j in tag_data[i]:
            tag_list.append(j)
        goal_tag[i] = random.choice(tag_list)
    for i in goal_tag:
        tags += "," + tag_data[i][goal_tag[i]]
    msg = f'头发是{goal_tag["发色"]}{goal_tag["头发"]},胸部{goal_tag["胸"]},穿着{goal_tag["衣服"]},{goal_tag["鞋子"]},{goal_tag["装饰"]},萌点是{goal_tag["二次元"]},身份是{goal_tag["身份"]}{goal_tag["类型"]}'
    return msg,tags

@sv.on_fullmatch(('今天我要变成少女!','今天我是什么少女'))
async def be_girl_exec(bot, ev):
    if (config['only_sd']):
        await be_girl_exec_sd(bot, ev)
        return
    uid = ev.user_id
    gid = ev.group_id
    name = ev.sender['nickname']
    msg,tags = await be_girl(uid)
    tags,error_msg,tags_guolv=await until.process_tags(gid,uid,msg) #tags处理过程
    if error_msg:
        await bot.finish(ev, error_msg)
    result_msg,error_msg = await until.get_imgdata(tags,way=0) #图片处理过程
    if error_msg:
        await bot.finish(ev, error_msg)
    msg = f"二次元少女{name},{msg}"
    msg = msg+ result_msg
    await bot.send(ev, msg)

@sv.on_fullmatch(('SD今天我是什么少女'))
async def be_girl_exec_sd(bot, ev):
    group_member_info = await bot.get_group_member_info(group_id = ev.group_id, user_id = ev.user_id)
    name = group_member_info['card'] if len(group_member_info['card']) != 0 else group_member_info['nickname']
    msg,tags_pre = await be_girl(ev.user_id)
    tags,error_msg,tags_guolv=await until.process_tags(ev.group_id, ev.user_id, tags_pre) #tags处理过程
    if error_msg:
        await bot.finish(ev, error_msg)
        return
    result_msg,error_msg = await until.get_imgdata_sd(tags,way = 0) #图片处理过程
    if error_msg:
        await bot.finish(ev, error_msg)
        return
    msg = f"二次元少女{name},{msg}"
    msg = msg+ result_msg
    await bot.send(ev, msg)

@sv.on_fullmatch(('今天我是什么烧鸡', 'SD今天我是什么烧鸡'))
async def be_girl_exec_sd_nsfw(bot, ev):
    # 检查nsfw配置
    error_msg = check_nsfw_conf(ev.group_id)
    if error_msg:
        await bot.finish(ev, error_msg)
        return

    group_member_info = await bot.get_group_member_info(group_id = ev.group_id, user_id = ev.user_id)
    name = group_member_info['card'] if len(group_member_info['card']) != 0 else group_member_info['nickname']
    msg,tags_pre = await be_girl(ev.user_id)
    tags,error_msg,tags_guolv=await until.process_tags(ev.group_id, ev.user_id, tags_pre, nsfw=True) #tags处理过程
    if error_msg:
        await bot.finish(ev, error_msg)
        return
    result_msg,error_msg = await until.get_imgdata_sd(tags,way = 0) #图片处理过程
    if error_msg:
        await bot.finish(ev, error_msg)
        return
    msg = f"二次元烧鸡{name},{msg}"
    msg = msg+ result_msg
    await bot.send(ev, msg)

@sv.on_prefix(('今天你是什么少女', 'SD今天你是什么少女'))
async def you_are_girl_exec_sd(bot, ev):
    sid = None
    gid = ev.group_id
    for m in ev.message:
        if m.type == 'at' and m.data['qq'] != 'all':
            sid = int(m.data['qq'])
        elif m.type == 'at' and m.data['qq'] == 'all':
            await bot.send(ev, '大家都变少女了~', at_sender=True)
            return
    if sid is None:
        await bot.finish(ev, '后面跟要@的人', at_sender=True)
        return
    group_member_info = await bot.get_group_member_info(group_id = gid, user_id = sid)
    name = group_member_info['card'] if len(group_member_info['card']) != 0 else group_member_info['nickname']
    msg,tags_pre = await be_girl(sid)
    tags,error_msg,tags_guolv=await until.process_tags(gid, sid, tags_pre) #tags处理过程
    if error_msg:
        await bot.finish(ev, error_msg)
        return
    result_msg,error_msg = await until.get_imgdata_sd(tags, way = 0) #图片处理过程
    if error_msg:
        await bot.finish(ev, error_msg)
        return
    msg = f"二次元少女{name},{msg}"
    msg = msg+ result_msg
    await bot.send(ev, msg)

@sv.on_prefix(('今天你是什么烧鸡', 'SD今天你是什么烧鸡'))
async def you_are_girl_exec_sd_r18(bot, ev):
    # 检查nsfw配置
    error_msg = check_nsfw_conf(ev.group_id)
    if error_msg:
        await bot.finish(ev, error_msg)
        return

    sid = None
    gid = ev.group_id
    for m in ev.message:
        if m.type == 'at' and m.data['qq'] != 'all':
            sid = int(m.data['qq'])
        elif m.type == 'at' and m.data['qq'] == 'all':
            await bot.send(ev, '大家都变烧鸡了~', at_sender=True)
            return
    if sid is None:
        await bot.finish(ev, '后面跟要@的人', at_sender=True)
    data1 = await bot.get_group_member_info(group_id = gid, user_id = sid)
    name = data1['card'] if len(data1['card']) != 0 else data1['nickname']
    msg,tags_pre = await be_girl(sid)
    tags,error_msg,tags_guolv=await until.process_tags(gid, sid, tags_pre, nsfw=True) #tags处理过程
    if error_msg:
        await bot.finish(ev, error_msg)
        return
    result_msg,error_msg = await until.get_imgdata_sd(tags,way=0) #图片处理过程
    if error_msg:
        await bot.finish(ev, error_msg)
        return
    msg = f"二次元烧鸡{name},{msg}"
    msg = msg+ result_msg
    await bot.send(ev, msg)

@sv.on_fullmatch(('少女抽卡', 'SD少女抽卡'))
async def girl_gacha_sd(bot, ev):
    seed = time.time()
    gid = ev.group_id
    random.seed(seed)
    rarity = random.randrange(1, 100)
    if rarity == 1:
        name = '★★★★★(PickUp)'
    elif rarity <= 5:
        name = '★★★★★'
    elif rarity <= 30:
        name = '★★★★'
    else:
        name = '★★★'
    msg, tags_pre = await be_girl(seed)
    tags, error_msg, tags_guolv = await until.process_tags(gid, ev.user_id, tags_pre) #tags处理过程
    if error_msg:
        await bot.finish(ev, error_msg)
        return
    result_msg,error_msg = await until.get_imgdata_sd(tags, way = 0) #图片处理过程
    if error_msg:
        await bot.finish(ev, error_msg)
        return
    msg = f"少女卡池抽卡, 抽到了{name}角色,{msg}"
    msg = msg + result_msg
    await bot.send(ev, msg, at_sender=True)

@sv.on_fullmatch(('烧鸡抽卡', 'SD烧鸡抽卡'))
async def girl_gacha_sd_r18(bot, ev):
    # 检查nsfw配置
    error_msg = check_nsfw_conf(ev.group_id)
    if error_msg:
        await bot.finish(ev, error_msg)
        return

    seed = time.time()
    gid = ev.group_id
    random.seed(seed)
    rarity = random.randrange(1, 100)
    if rarity == 1:
        name = '★★★★★(PickUp)'
    elif rarity <= 5:
        name = '★★★★★'
    elif rarity <= 30:
        name = '★★★★'
    else:
        name = '★★★'
    msg, tags_pre = await be_girl(seed)
    tags, error_msg, tags_guolv = await until.process_tags(gid, ev.user_id, tags_pre, nsfw=True) #tags处理过程
    if error_msg:
        await bot.finish(ev, error_msg)
        return
    result_msg,error_msg = await until.get_imgdata_sd(tags, way = 0) #图片处理过程
    if error_msg:
        await bot.finish(ev, error_msg)
        return
    msg = f"烧鸡卡池抽卡, 抽到了{name}角色,{msg}"
    msg = msg + result_msg
    await bot.send(ev, msg, at_sender = True)