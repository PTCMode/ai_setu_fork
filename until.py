from base64 import b64encode
from io import BytesIO
import re
from heapq import nsmallest
from hoshino import aiorequests
from PIL import Image, ImageDraw,ImageFont
import base64
import time,calendar
import math
from . import translate,db,easygradio
import asyncio
import aiofiles
import uuid
import difflib
import random
from .util import *


async def get_models():
    url = f"{config['sd_api_ip']}/sdapi/v1/sd-models"
    response = await aiorequests.get(url,headers = {"Content-Type": "application/json"})
    modeldata = await response.json()
    model_list, model_name= [],[]
    for i in modeldata:
        model_list.append(i["title"])
        model_name.append(i["model_name"])
    return model_list


async def get_model_list():
    url = f"{config['sd_api_ip']}/sdapi/v1/options"
    response = await aiorequests.get(url,headers = {"Content-Type": "application/json"})
    optionsdata = await response.json()
    msg = f"\n正在使用的模型：\n{optionsdata['sd_model_checkpoint']}\n模型列表:\n"
    model_list = await get_models()
    msg1 = "\n".join(model_list) if model_list else "无"
    msg += msg1
    return msg

async def change_model(msg):
    model = msg.strip()
    model_list = await get_models()
    if model in model_list:
        url = f"{config['sd_api_ip']}/sdapi/v1/options"
        data = {"sd_model_checkpoint":model}
        response = await aiorequests.post(url,headers = {"Content-Type": "application/json"},json=data)
        optionsdata = await response.json()
        if optionsdata:
            return f"模型切换失败"
    else:
        return f"模型切换失败"


async def guolv(text):#过滤屏蔽词
    text_lc = text.lower() #转为小写
    tags_guolv = ""
    for i in actree.iter(text_lc):
        text = re.sub(i[1][1], "", text, flags = re.IGNORECASE)
        tags_guolv = f"{tags_guolv} {str(i[1][1])} "
    return text,tags_guolv

async def guolv_r18(text):#过滤屏蔽词
    text_lc = text.lower() #转为小写
    tags_guolv = ""
    for i in actree_r18.iter(text_lc):
        text = re.sub(i[1][1], "", text, flags = re.IGNORECASE)
        tags_guolv = f"{tags_guolv} {str(i[1][1])} "
    return text,tags_guolv

def match_and_add(tags, ntags):
    text_lc = tags.lower() #转为小写
    for name in actrees_for_match:
        for i in actrees_for_match[name].iter(text_lc):
            if i:
                for item in config['add_on_match_prompt']:
                    if list(item)[0] == name:
                        if item[list(item)[0]]["tags"]:  tags  = f'{tags},{item[list(item)[0]]["tags"]}'
                        if item[list(item)[0]]["ntags"]: ntags = f'{ntags},{item[list(item)[0]]["ntags"]}'
                        break
                break
    return tags, ntags

async def process_tags(gid, uid, tags, add_db = config['add_db'], trans = config['trans'],\
                       limit_word = config['limit_word'], arrange_tags = config['arrange_tags'],\
                       sfw = True, nsfw = False):
    error_msg ="" #报错信息
    tags_guolv="" #过滤词信息
    #初始化
    try:
        tags = f"tags={tags.strip()}" #去除首尾空格换行#头部加上tags=
        taglist = re.split('&',tags) #分割
        # taglist[0] = taglist[0].strip().lower() #转小写方便处理
        taglist[0] = taglist[0].strip() # FIXME: 直接转小写会把Lora也一起转换, 造成识别不出Lora的现象
        id = ["tags=","ntags=","def_tags=","seed=","scale=","shape=","strength=","r18=","steps=","sampler=","restore_faces=","tiling=","bigger=","hr_scale=","w=","h="]
        #取出tags+ntags+seed+scale+shape,每种只取列表最后一个,并删掉id
        tag_dict = {i: ("" if not [idx for idx in taglist if idx.startswith(i)] \
                        else [idx for idx in taglist if idx.startswith(i)][-1]).replace(i, '', 1)  for i in id }
    except Exception as e:
        error_msg = f"tags初始化失败{e}"
        return tags,error_msg,tags_guolv
    #翻译tags
    if trans:
        try:
            if tag_dict["tags="] and tag_dict["ntags="]:
                tags2trans = f'{tag_dict["tags="]}&{tag_dict["ntags="]}' # &作为分隔符,为了整个拿去翻译
                tags2trans = await translate.tag_trans(tags2trans) #翻译
                taglist1 = re.split('&',tags2trans)
                tag_dict["tags="] = taglist1[0]
                tag_dict["ntags="] = taglist1[1]
            elif tag_dict["tags="]:
                tag_dict["tags="] = await translate.tag_trans(tag_dict["tags="])#翻译
        except Exception as e:
            error_msg += "翻译失败"

    #过滤tags,只过滤正面tags
    if limit_word:
        try:
            tags_guolv_1, tags_guolv_2 = '', ''
            text = tag_dict["tags="].strip()
            if sfw and not nsfw:
                text,tags_guolv_1 = await guolv_r18(text) #过滤, 转小写防止翻译出来大写
            text,tags_guolv_2 = await guolv(text)
            tag_dict["tags="] = text
            tags_guolv = f'{tags_guolv_1},{tags_guolv_2}' if tags_guolv_1 and tags_guolv_2 else f'{tags_guolv_1}{tags_guolv_2}'
        except Exception as e:
            error_msg += "过滤失败"

    #整理tags
    if arrange_tags:
        try:
            #整理tags,去除空元素,去除逗号影响
            id2tidy = ["tags=","ntags="]
            for i in id2tidy:
                tidylist = re.split(',|，',tag_dict[i])
                while "" in tidylist:
                    tidylist.remove("")
                tag_dict[i] = ",".join(tidylist)
        except Exception as e:
            error_msg += f"整理失败{e}"

    #规范tags
    if (not tag_dict["def_tags="] and config['add_default_prompt']) or tag_dict["def_tags="] == 'True':
        tag_dict["tags="]  = f'{config["tags_moren"]},{tag_dict["tags="]}'      if tag_dict["tags="]    else config["tags_moren"]
        tag_dict["ntags="] = f'{config["ntags_moren"]},{tag_dict["ntags="]}'    if tag_dict["ntags="]   else config["ntags_moren"]
    else:
        if not tag_dict["tags="]:
            tag_dict["tags="] = config['tags_moren']#默认正面tags
        if not tag_dict["ntags="]:
            tag_dict["ntags="] = config['ntags_moren']#默认负面tags

    if sfw and not nsfw:
        tag_dict["tags="] = (f"{config['tags_sfw']},{tag_dict['tags=']}")
        tag_dict["ntags="] = (f"{config['ntags_sfw']},{tag_dict['ntags=']}")
    elif nsfw:
        tag_dict["tags="] = (f"{config['tags_nsfw']},{tag_dict['tags=']}")
        tag_dict["ntags="] = (f"{config['ntags_nsfw']},{tag_dict['ntags=']}")

    if config['add_on_match']:
        tags_tmp  = tag_dict["tags="].strip()
        ntags_tmp = tag_dict["ntags="].strip()
        tag_dict["tags="], tag_dict["ntags="] = match_and_add(tags_tmp, ntags_tmp)

    if tag_dict["shape="] and tag_dict["shape="] in ["portrait","landscape","square","portrait_pony","landscape_pony","square_pony"]:
        tag_dict["shape="] = tag_dict["shape="].capitalize()
    else:
        tag_dict["shape="] = config['txt2img_shape_moren']#默认形状

    if not tag_dict["r18="]:
        tag_dict["r18="] = config['r18_moren']#默认r18参数
    if not tag_dict["restore_faces="] and tag_dict["restore_faces="] != "True":
        tag_dict["restore_faces="] = False#默认restore_faces
    if not tag_dict["tiling="] and tag_dict["tiling="] != "True":
        tag_dict["tiling="] = False#默认tiling
    tag_dict["bigger="] = False if not tag_dict["bigger="] else True#默认bigger
    #上传XP数据库
    if add_db:
        try:
            #上传XP数据库,只上传正面tags
            tags2XP = tag_dict["tags="]
            taglist3 = re.split(',',tags2XP)
            for tag in taglist3:
                db.add_xp_num(gid,uid,tag)
        except Exception as e:
            error_msg += "上传失败"
    return tag_dict,error_msg,tags_guolv

async def retry_get_ip_token(i):
    if i < len(ip_token_list):
        api_ip,token = ip_token_list[i]
    return api_ip,token

#pic本地保存
#pid
async def pic_save_temp(imagedata):
    pid = str(uuid.uuid4())
    async with aiofiles.open(f"{temp_image_path}/{pid}.png", 'wb') as f:
        await f.write(imagedata)
    return pid


async def pic_resize(width,height):
    c = width/height
    n = config["pic_max"] #最大像素
    if width*height > n:
        height = math.ceil(math.sqrt(n/c))
        width = math.ceil(c*height)
    width = math.ceil(width/64)*64
    height = math.ceil(height/64)*64 #等比缩放为64的倍数
    return width,height



async def get_pic_msg_temp(msg):
    try:
        pid = re.search(r"pid:+([a-z0-9-]{36})",str(msg))[1]
        img = Image.open(f"{temp_image_path}/{pid}.png")
    except:
        return f"找不到这个图片涅~"
    try:
        msg = img.info["parameters"]
        parameters = re.search(r"(.+)\nNegative prompt: +(.+)\nSteps: +(.+), Sampler: +(.+), CFG scale: +(.+), Seed: +(.+), Size: +(.+), Model hash: +(.{8})",msg)
        msg = f'''
▲prompt: {parameters[1]}
▼Negative prompt: {parameters[2]}
Steps:{parameters[3]}  Sampler:{parameters[4]}
CFG scale:{parameters[5]}  seed:{parameters[6]}
Size:{parameters[7]}  Model hash:{parameters[8]}
FROM STABLE DIFFUSION WEBUI'''
    except:
        a,b= img.info["Description"],eval(img.info["Comment"])
        msg = f'''
▲prompt: {a}
▼Negative prompt: {b["uc"]}
Steps:{b["steps"]}  Sampler:{b["sampler"]}
CFG scale:{b["scale"]}  seed:{b["seed"]}
FROM NOVELAI'''
    return msg

#get_pic_descrip
async def get_pic_descrip_(b_io):
  try:
      url = f"{config['sd_api_ip']}/sdapi/v1/interrogate"
      data = "data:image/jpeg;base64," + base64.b64encode(b_io.getvalue()).decode()
      json_data = {
        "image": data,
        "model": "clip",
      }
      response = await aiorequests.post(url,json=json_data,headers = {"Content-Type": "application/json"})
      msgdata = await response.json()#报错反馈,待完成
      msg = re.search(r"(.*),", msgdata["caption"])[1]
      if config['trans']:
          try:
              msg_trans = await translate.txt_trans(msg,way=0)#翻译
              msg = f"\nEnglish:\n{msg}\n中文:\n{msg_trans}"
          except:
              msg = f"\nEnglish:\n{msg}"
      else:
          msg = f"\nEnglish:\n{msg}"
  except Exception as e:
        msg = "观察失败"
  return msg

async def get_pic_strong_(b_io):
    try:
        url = f"{config['sd_api_ip']}/sdapi/v1/interrogate"
        data = "data:image/jpeg;base64," + base64.b64encode(b_io.getvalue()).decode()
        json_data = {
          "image": data,
          "model": "clip",
        }
        response = await aiorequests.post(url,json=json_data,headers = {"Content-Type": "application/json"})
        msgdata = await response.json()#报错反馈,待完成
        msg = re.search(r"(.*),", msgdata["caption"])[1]
    except:
        return "获取增强信息失败"
    tags = r"{{highly detailed}},{{masterpiece}},{ultra-detailed},{illustration},{{best quality}}," + msg
    tags,error_msg,tags_guolv = await process_tags(0,0,tags,0,0,0,0)
    result_msg,error_msg = await get_imgdata_sd(tags,way=0,shape="Portrait",b_io=b_io,size = None)
    if error_msg:
        return result_msg
    result_msg = f"\n{msg}\n{result_msg}"
    return result_msg


#way=0是txt2img,way=1是img2img
async def get_imgdata_sd(tagdict:dict,way=1,shape="Portrait",b_io=None,size = None):
    error_msg =""  #报错信息
    result_msg = ""
    if not tagdict["seed="]:
        tagdict["seed="] = -1
    if not way:
        shape = tagdict["shape="]
        if shape.lower() == "portrait":
            width,height = 512,768
        elif shape.lower() == "landscape":
            width,height = 768,512
        elif shape.lower() == "square":
            width,height = 640,640
        elif shape.lower() == "portrait_pony":
            width,height = 832,1216
        elif shape.lower() == "landscape_pony":
            width,height = 1216,832
        elif shape.lower() == "square_pony":
            width,height = 1040,1040
        if tagdict["bigger="]:
            width,height = width+128,height+128
        if tagdict["w="] and tagdict["w="].isdigit():
            width = int(tagdict["w="])
        if tagdict["h="] and tagdict["h="].isdigit():
            height = int(tagdict["h="])
        width,height = await pic_resize(width,height)#修正生成图的长宽为SD要求的64的倍数
        if not tagdict["steps="] or not tagdict["steps="].isdigit():
            tagdict["steps="] = config["txt2img_steps_moren"] #默认steps
        else:
            tagdict["steps="] = config["txt2img_steps_moren"]  if int(tagdict["steps="])>config["txt2img_steps_max"]  else tagdict["steps="]#超过最大步数
        if not tagdict["sampler="]:
            tagdict["sampler="] = config["txt2img_sampler_moren"]#默认sampler
        if not tagdict["scale="]:
            tagdict["scale="] = config['txt2img_scale_moren']#默认scale
        url = f"{config['sd_api_ip']}/sdapi/v1/txt2img"
        json_data = {
            "prompt": tagdict["tags="],
            "negative_prompt": tagdict["ntags="],
            "seed": tagdict["seed="],
            "steps": tagdict["steps="],
            "cfg_scale": tagdict["scale="],
            "width": width,
            "height": height,
            "denoising_strength": 0,
            "restore_faces": tagdict["restore_faces="],
            "tiling": tagdict["tiling="],
            "sampler_index": tagdict["sampler="],
            "scheduler": "Automatic",
            "enable_hr": config['enable_hr'],
            "hr_scale": tagdict["hr_scale="] if tagdict["hr_scale="] else config['hr_scale'],
            "hr_upscaler": config['hr_upscaler'],
            "hr_scheduler": "Automatic",
            "hr_additional_modules": [
                "Use same choices"
            ],
            "hr_second_pass_steps": config['hr_second_pass_steps'],
            "denoising_strength": config['hr_denoising_strength']
        }

    if way :
        url = f"{config['sd_api_ip']}/sdapi/v1/img2img"
        data = ["data:image/jpeg;base64," + base64.b64encode(b_io.getvalue()).decode()]
        width,height = size
        if tagdict["bigger="]:
            width,height = width*2,height*2
        width,height = await pic_resize(width,height)#修正生成图的长宽为SD要求的64的倍数
        if not tagdict["strength="]:
            tagdict["strength="] = config['img2img_strength_moren']#默认噪声
        if not tagdict["steps="] or not tagdict["steps="].isdigit():
            tagdict["steps="] = config["img2img_steps_moren"] #默认steps
        else:
            tagdict["steps="] = config["img2img_steps_moren"] if int(tagdict["steps="]) > config["img2img_steps_max"] else tagdict["steps="]#超过最大步数
        if not tagdict["sampler="]:
            tagdict["sampler="] = config["img2img_sampler_moren"]#默认sampler
        if not tagdict["scale="]:
            tagdict["scale="] = config['img2img_scale_moren']#默认scale
        json_data = {
            "init_images": data,
            "resize_mode": config["resize_mode"],
            "denoising_strength": tagdict["strength="],
            "prompt": tagdict["tags="],
            "negative_prompt": tagdict["ntags="],
            "seed": tagdict["seed="],
            "steps": tagdict["steps="],
            "cfg_scale": tagdict["scale="],
            "width": width,
            "height": height,
            "denoising_strength": 0,
            "restore_faces": tagdict["restore_faces="],
            "tiling": tagdict["tiling="],
            "sampler_index": tagdict["sampler="],
            "scheduler": "Automatic",
            "enable_hr": config['enable_hr'],
            "hr_scale": tagdict["hr_scale="] if tagdict["hr_scale="] else config['hr_scale'],
            "hr_upscaler": config['hr_upscaler'],
            "hr_scheduler": "Automatic",
            "hr_additional_modules": [
                "Use same choices"
            ],
            "hr_second_pass_steps": config['hr_second_pass_steps'],
            "denoising_strength": config['hr_denoising_strength']
        }
    response = await aiorequests.post(url,json=json_data,headers = {"Content-Type": "application/json"})
    imgdata = await response.json()#报错反馈,待完成
    imgdata = imgdata["images"][0]
    try :
        pid = await pic_save_temp(base64.b64decode(imgdata))
    except Exception as e:
        print(f"!!!保存失败{e}")
    try:
        imgmes = 'base64://' + imgdata
    except Exception as e:
        error_msg = f"处理图像失败{e}"
        return result_msg,error_msg
    result_msg = f"[CQ:image,file={imgmes}]\npid:{pid}"
    return result_msg,error_msg


async def get_imgdata(tagdict:dict,way=1,shape="Portrait",b_io=None):#way=0时为get，way=1时为post
    error_msg =""  #报错信息
    result_msg = ""
    if not way and not tagdict["strength="]:
        tagdict["strength="] = config['img2img_strength_moren']#默认噪声
    #合并tags
    tags = tagdict["tags="]
    id = ["tags=","ntags=","seed=","scale=","shape=","strength=","r18="]
    for i in id:
        if i != "tags=" and tagdict[i]:
            tags += f"&{i}{tagdict[i]}"
    i = 0
    while i < len(ip_token_list):
        await asyncio.sleep(1) #防止过快
        i+=1
        print(f"第{i}次查询")
        api_ip,token = await retry_get_ip_token(i-1)
        try:
            if not way:
                url = (f"http://{api_ip}/got_image") + (f"?tags={tags}")+ (f"&token={token}")
                response = await aiorequests.get(url, timeout=180)
            else:
                url = (f"http://{api_ip}/got_image2image") + (f"?tags={tags}")+(f"&token={token}")
                response = await aiorequests.post(url,data=b64encode(b_io.getvalue()), timeout=180)
            imgdata = await response.content
            if len(imgdata) < 5000:
                error_msg = "token冷却中~"
                continue
        except Exception as e:
            error_msg = f"超时了~"
            continue
        i=999
        error_msg = ""
    if error_msg:
        return result_msg,error_msg
    try :
        pid = await pic_save_temp(imgdata)
    except Exception as e:
        print(f"!!!保存失败{e}")
    try:
        img = Image.open(BytesIO(imgdata))
        buffer = BytesIO()  # 创建缓存
        img.save(buffer, format="PNG")
        imgmes = 'base64://' + b64encode(buffer.getvalue()).decode()
    except Exception as e:
        error_msg = f"处理图像失败{e}"
        return result_msg,error_msg
    result_msg = f"[CQ:image,file={imgmes}]\npid:{pid}"
    return result_msg,error_msg


async def get_xp_list_(msg,gid,uid):
    error_msg =""  #报错信息
    result_msg = ""
    if msg == "本群":
        xp_list = db.get_xp_list_group(gid)
    elif msg == "个人":
        xp_list = db.get_xp_list_personal(gid,uid)
    else:
        error_msg = "参数错误"
        return result_msg,error_msg
    result_msg = f'{msg}的XP排行榜为：\n'
    if len(xp_list)>0:
        for xpinfo in xp_list:
            keyword, num = xpinfo
            result_msg = result_msg + (f'关键词：{keyword}||次数：{num}\n')
    else:
        result_msg = f'暂无{msg}的XP信息'
    return result_msg,error_msg

async def get_xp_pic_(msg,gid,uid):
    error_msg =""  #报错信息
    result_msg = ""
    if msg == "本群":
        xp_list = db.get_xp_list_kwd_group(gid)
    elif msg == "个人":
        xp_list = db.get_xp_list_kwd_personal(gid,uid)
    else:
        error_msg = "参数错误"
        return result_msg,error_msg
    if len(xp_list)>0:
        keywordlist = []
        for (a,) in xp_list:
            keywordlist.append(a)
        tags = (',').join(keywordlist)
        result_msg = tags
    else:
        error_msg = f'暂无{msg}的XP信息'
    return result_msg,error_msg

# FIXME: 获取图像功能更新QQ后不可用
async def get_pic_d(msg):
    error_msg = ""  # 报错信息
    try:
        image_url = re.search(r"\[CQ:image,file=(.*)url=(.*?)[,\];]", str(msg))
        url = image_url.group(2)
        print(url)
        # url = re.sub('https:', 'http:', url)
    except Exception as e:
        error_msg = "你的图片呢？"
        return None,None,error_msg,None
    try:
        b_io = BytesIO()
        shape = ''
        size = None

        img_data = await aiorequests.get(url)
        image = Image.open(BytesIO(await img_data.content))
        a,b = image.size
        c = a/b
        s = [0.6667,1.5,1]
        size = (a,b)
        s1 =["Portrait","Landscape","Square"]
        shape=s1[s.index(nsmallest(1, s, key=lambda x: abs(x-c))[0])]#判断形状
        image = image.convert("RGB")
        image.save(b_io, format="JPEG")

    except Exception as e:
        error_msg = "图片处理失败" # 报错信息
        return b_io,shape,error_msg,size
    return b_io,shape,error_msg,size

async def img_make(msglist,page = 1):
    num = len(msglist)
    max_row = math.ceil(num/4)
    target = Image.new('RGB', (1920,512*max_row),(255,255,255))
    page = page - 1
    idlist,imglist,thumblist = [],[],[]
    for (a,b,c) in msglist:
        idlist.append(a)
        imglist.append(b)
        thumblist.append(c)
    for index in range(0+(page*config['per_page_num']),(config['per_page_num']+(page*config['per_page_num']))):
        try:
            id = f"ID: {idlist[index]}" #图片ID
            thumb = f"点赞: {thumblist[index]}" #点赞数
            image_path= str(imglist[index]) #图片路径
        except:
            break
        region = Image.open(image_path)
        region = region.convert("RGB")
        region = region.resize((int(region.width/2),int(region.height/2)))
        font = ImageFont.truetype(font_path, 36)  # 设置字体和大小
        draw = ImageDraw.Draw(target)
        row = math.ceil((index+1)/4)
        column= (index+1)%4+1
        target.paste(region,(80*column+384*(column-1),50+100*(row-1)+384*(row-1)))
        draw.text((80*column+384*(column-1)+int(region.width/2)-90,80+100*(row-1)+384*(row-1)+region.height),id,font=font,fill = (0, 0, 0))
        draw.text((80*column+384*(column-1)+int(region.width/2)+20,80+100*(row-1)+384*(row-1)+region.height),thumb,font=font,fill = (0, 0, 0))
    result_buffer = BytesIO()
    target.save(result_buffer, format='JPEG', quality=90) #质量影响图片大小
    imgmes = 'base64://' + base64.b64encode(result_buffer.getvalue()).decode()
    result_msg = f"[CQ:image,file={imgmes}]"
    return result_msg

async def check_pic_(gid,uid,msg):
    error_msg = ""
    msg = re.search("(.{2})\s*([0-9]*)", str(msg))
    page = 1 if not msg[2] else int(msg[2])
    num = page*config['per_page_num']
    if msg[1] == "本群":
        msglist = db.get_pic_list_group(gid,num)
    elif msg[1] == "个人":
        msglist = db.get_pic_list_personal(uid,num)
    elif msg[1] == "全部":
        msglist = db.get_pic_list_all(num)
    else:
        error_msg = "参数错误"
        return result_msg,error_msg
    if len(msglist) == 0:
        error_msg = f"无法找到{msg}图片信息"
        return result_msg,error_msg
    result_msg = await img_make(msglist,page)
    return result_msg,error_msg

async def save_pic(data):
    error_msg = ""
    pic_hash = ""
    pic_dir = ""
    try:
        pic_hash = hash(data)
        datetime = calendar.timegm(time.gmtime())
        image_path= './SaveImage/'+str(datetime)+'.jpg'
        pic_dir = join(curpath, f'{image_path}')#hash与savepath
        pic = open(pic_dir, "wb")
        pic.write(data)
        pic.close() #保存图片
    except Exception as e:
        error_msg = "图片保存失败"
        return pic_hash,pic_dir,error_msg
    return pic_hash,pic_dir,error_msg


async def img2anime_(message,msg):
    error_msg = ""
    result_msg = ""
    if not config['img2anime']:
        error_msg = "未开启动漫化功能"
        return result_msg,error_msg
    b_io,shape,error_msg,size = await get_pic_d(message)
    if error_msg != "":
        return result_msg,error_msg
    json_data = ["data:image/jpeg;base64," + base64.b64encode(b_io.getvalue()).decode()]
    result_msg,error_msg = await easygradio.predict_push_(config['img2anime_url'],json_data,max_try=config['img2anime_url_timeout'])
    if error_msg != "":
        return None,error_msg
    result_msg = result_msg[0]
    result_img = base64.b64decode(''.join(result_msg.split(',')[1:]))
    result_img = Image.open(BytesIO(result_img)).convert("RGB")
    buffer = BytesIO()  # 创建缓存
    result_img.save(buffer, format="png")
    img_msg = 'base64://' + b64encode(buffer.getvalue()).decode()
    result_msg = f"[CQ:image,file={img_msg}]"
    return result_msg,error_msg

async def img2tags_(message,msg):
    result_msg = ""
    error_msg = "" #报错信息
    if not config['img2tag']:
        error_msg = "未开启鉴赏图片功能"
        return result_msg,error_msg
    b_io,shape,error_msg,size = await get_pic_d(message)
    if error_msg != "":
        return result_msg,error_msg
    json_data = ["data:image/jpeg;base64," + base64.b64encode(b_io.getvalue()).decode(),0.7]
    result_msg,error_msg = await easygradio.predict_push_(config['img2tags_url'],json_data,max_try=config['img2tags_url_timeout'])
    if error_msg != "":
        return None,error_msg
    result_msg = result_msg[1]
    #result_msg = result_msg['confidences']
    #result_msg = ','.join([f'{i["label"]}' for i in result_msg]).replace("rating:safe,","")
    result_msg = f"\n鉴赏出的tags有:\n{result_msg}"
    return result_msg,error_msg

async def pic_super_(message,msg):
    error_msg = ""
    result_msg = ""
    if not config['picsuper']:
        error_msg = "未开启图片超分"
        return result_msg,error_msg
    b_io,shape,error_msg,size = await get_pic_d(message)
    a,b = size
    if error_msg != "":
        return result_msg,error_msg
    if a*b > config['max_size']:
        error_msg = "图片这么大，进不去拉~"
        return result_msg,error_msg
    try:
        if "2倍超分" in msg:
            scale = 2
        elif "3倍超分" in msg:
            scale = 3
        elif "4倍超分" in msg:
            scale = 4
        else:
            scale = 2
        if "保守降噪" in msg:
            con = "conservative"
        elif "无降噪" in msg:
            con = "no-denoise"
        elif "降噪" in msg:
            con = "denoise3x"
        else:
            con = "denoise3x"
        modelname = f"up{scale}x-latest-{con}.pth" if "专业" not in msg or scale == 4 else f"up{scale}x-pro-{con}.pth"
    except Exception as e:
        error_msg = error_msg.join("超分参数错误")
        return result_msg,error_msg
    json_data = ["data:image/jpeg;base64," + base64.b64encode(b_io.getvalue()).decode(),modelname,2]
    result_msg,error_msg = await easygradio.predict_push_(config['pic_super_url'],json_data,max_try=config['pic_super_timeout'])
    if error_msg != "":
        return None,error_msg
    result_msg = result_msg[0]
    result_msg = result_msg.split("base64,")[1]
    result_msg = 'base64://' + result_msg
    result_msg = f"[CQ:image,file={result_msg}]"
    return result_msg,error_msg


async def mix_magic_(msg):
    error_msg = ""
    magic_msg = ""
    magic_msg_pure = ""
    magic_id_list = re.split('\\s+',msg)
    num = config["max_magic_num"]
    for i in magic_id_list:
        if i in magic_data_title and num:
            magic_msg += f'{magic_data[i]["tags"]},'
            magic_msg_pure += f'{magic_data_pure[i]["tags"]},'
            magic_msg_ntag = magic_data[i]["ntags"]
            magic_msg_scale = magic_data[i]["scale"]
            num -=1
    if not magic_msg:
        error_msg = "发动魔法失败"
        return error_msg,None,None,None
    magic_list = re.split(',',magic_msg)
    magic_list_pure = re.split(',',magic_msg_pure)
    for i in range(len(magic_list)-1,-1,-1):
        j=i-1
        if i == 0:
            break
        for j in range(j,-1,-1):
            seq=  difflib.SequenceMatcher(lambda x: x ==" ",magic_list_pure[i],magic_list_pure[j])
            if seq.ratio()> config['max_ratio']: #相似度大于0.8则删除
                magic_list[j] = ""
                magic_list_pure[j] = ""
    while "" in magic_list:
        magic_list.remove("")
    magic_msg_tag = ",".join(magic_list)
    if "咏唱" in msg:
        dark = random.choice(magic_data_dark_title)
        magic_msg_tag += f'{magic_data_dark[dark]["tags"]},'
        magic_msg_ntag = magic_data_dark[dark]["ntags"]
    return error_msg,magic_msg_tag,magic_msg_ntag,magic_msg_scale
    #融合魔法以最后融合的魔法作为基准!!!

async def get_magic_book_(msg):
    error_msg = ""
    error_msg,magic_msg_tag,magic_msg_ntag,magic_msg_scale = await mix_magic_(msg) #获取魔法书
    if error_msg != "":
        return None,error_msg,None
    result_msg = magic_msg_tag +"&ntags="+ magic_msg_ntag +"&shape=Landscape"+"&scale=" + magic_msg_scale
    tag_dict,error_msg,tags_guolv = await process_tags(1,1,result_msg,0,0,0,0)
    return tag_dict,error_msg
