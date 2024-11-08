from hoshino import aiorequests
import uuid
import hashlib
import time
import re
from deepl import Translator as DeepLTranslator
from pygoogletranslation import Translator as GoogleTranslator
from .util import config


async def googleTranslate(translate_text:str) -> str:
    proxy={"http":"127.0.0.1:7890","https":"127.0.0.1:7890"}
    translator=GoogleTranslator(proxies=proxy)
    result = translator.translate(translate_text,src='zh-cn',dest='en')
    return result.text


async def deepLTranslate(translate_text:str, url = config['deepl_url'], app_key = config['deepl_app_key'], proxy = config['deepl_proxy']) -> str:
    translator = DeepLTranslator(app_key, server_url = url, proxy = proxy) 
    result = translator.translate_text(translate_text, target_lang = 'EN-GB')
    return result.text


async def youdaoTranslate(translate_text, url = config['youdao_url'], app_id = config['youdao_app_id'], app_key = config['youdao_app_key']):
    '''
    :param translate_text: 待翻译的句子
    :param flag: 1:原句子翻译成英文；0:原句子翻译成中文
    :return: 返回翻译结果
    '''

    # 翻译文本生成sign前进行的处理
    input_text = ""

    # 当文本长度小于等于20时，取文本
    if (len(translate_text) <= 20):
        input_text = translate_text

    # 当文本长度大于20时，进行特殊处理
    elif (len(translate_text) > 20):
        input_text = translate_text[:10] + str(len(translate_text)) + translate_text[-10:]

    time_curtime = int(time.time())  # 秒级时间戳获取
    uu_id = uuid.uuid4()  # 随机生成的uuid数，为了每次都生成一个不重复的数。

    sign = hashlib.sha256(
        (app_id + input_text + str(uu_id) + str(time_curtime) + app_key).encode('utf-8')).hexdigest()  # sign生成

    data = {
        'q': translate_text,  # 翻译文本
        'appKey': app_id,  # 应用id
        'salt': uu_id,  # 随机生产的uuid码
        'sign': sign,  # 签名
        'signType': "v3",  # 签名类型，固定值
        'curtime': time_curtime,  # 秒级时间戳
    }
    data['from'] = "zh-CHS"  # 译文语种
    data['to'] = "en"  # 译文语种

    result = await aiorequests.get(url, params=data)  # 获取返回的json()内容
    result = await result.json()
    # print("翻译后的结果：" + result["translation"][0])  # 获取翻译内容
    return result["translation"][0]


async def baiduTranslate(translate_text:str, url = config['baidu_url'], app_id = config['baidu_app_id'], app_key = config['baidu_app_key']) -> str:
    from_lang = 'zh'  # original language
    to_lang = 'en'  # target language
    # get text to translate
    input_text = '这里是需要翻译的内容。'
    input_text = translate_text

    # Generate salt and sign
    uu_id = uuid.uuid4()
    sign = hashlib.md5((app_id + input_text + str(uu_id) + app_key).encode('utf-8')).hexdigest()

    # Build request
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {
        'appid': app_id,
        'q': input_text,
        'from': from_lang,
        'to': to_lang,
        'salt': uu_id,
        'sign': sign
    }

    # Send request
    result = await (await aiorequests.post(url, params=data, headers=headers)).json()

    # Show response
    return result["trans_result"][0]["dst"]


async def tag_trans(tags : str):
    last_index = 0
    while last_index < len(tags) - 1:
        start, end = -1, -1
        for index in range(last_index, len(tags)):
            last_index = index
            if ('\u4e00' <= tags[index] <= '\u9fa5'):
                if start == -1:
                    start = index
                if not (start != -1 and index == len(tags) - 1):
                    continue

            if start != -1:
                end = index if (index != len(tags) - 1) else (index + 1)
                sousce = tags[start:end]
                transleted = await txt_trans(sousce)
                tags = re.sub(sousce, transleted, tags, 1)
                last_index = index - len(sousce) + len(transleted)
                break
    return tags


async def txt_trans(text):
    if config['way2trans'] == 0:
        ret = await youdaoTranslate(text)
    if config['way2trans'] == 1:
        ret = await baiduTranslate(text)
    if config['way2trans'] == 2:
        ret = await deepLTranslate(text)
    if config['way2trans'] == 3:
        ret = await googleTranslate(text)
    print(f'Translate: "{text}" -> "{ret}"')
    return ret