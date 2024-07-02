'''
Author: Dean
Date: 2023-11-18 21:03:56
LastEditTime: 2024-07-03 01:11:09
LastEditors: your name
Description: 
FilePath: \python\wenzhi_rag_framework_text_slice\src\doc_analyze.py
可以输入预定的版权声明、个性签名、空行等
'''
from datetime import datetime
import json
from uuid import uuid4
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModel
import torch
import numpy as np
import fitz
from PIL import Image
import io
import re
import pandas as pd
from paddleocr import PaddleOCR
import cv2
import numpy as np
import os
from openai import OpenAI
from docx import Document
from docx.oxml.table import CT_Tbl
from docx.table import _Cell, Table
from docx.oxml.text.paragraph import CT_P
from docx.text.paragraph import Paragraph
import random
import win32com.client
import tabula
import pdfplumber
# from chinese_splitter import ChineseRecursiveTextSplitter
from splitter_overlap import RecursiveTextSplitter

model_path = r'..\..\machine_learning\layered_plus_ques_rag\model\tao-8k'
special_symbol = ['\n', '\r', '!', '@', '#', '$', '%', '^', '&', '*', '_', '+', '=', '`', '~', '[', ']', '{', '}', '\\', '|', ';', ':', ',', '<',  '>', '/', '?', '！', '￥', '…', '—', '【', '】', '：', '，', '。', '？', '～']
sentense_symbol_chinese = ['\n', '。', '！', '?', '？', '；', ';']
sentense_symbol_none_chinese = ['\n', '.', '!', '?', ';']


emb_model = SentenceTransformer(model_path).to('cuda') if torch.cuda.is_available() else SentenceTransformer(model_path)

api_keys_openai = []

prompt_template_heading_level = """[命令区]:
1. 请根据以下标题内容，生成对应的标题级别
2. 标题级别1级最高
3. 每个标题只有一个级别
4. 判断标题级别时，低级别标题从属于高级别标题，将从属关系表示出来
5. 请遵循json输出格式，具体形式参考格式区示例，不要输出json以外的内容
6. 待判断的标题为：[{titles}]
[格式区]:
{
    "title1":{
        "level":1,
        "sub_title":{
            "title2":{
                "level":2,
                "sub_title":{
                    "title3":{
                        "level":3
                    }
                }
            }
            
        }
    },
    "title4":{
        "level":1,
        "sub_title":{
        }
    }
}
"""

def chat_once_openai(messages, model='gpt-4o'):
    client = OpenAI(api_key="sk-8fDrTx0A87Akz0g4Vpj4J25RHhigwKVRjyUsryLD0vAPCyyd", base_url='https://api.chatanywhere.com.cn/v1')
    response = response = client.chat.completions.create(
        model=model,
        messages = messages
    )
    ans = response.choices[0].message.content
    return ans

def chat_once_retry(messages, chat_type, model, retry_time = 5):
    while retry_time > 0:
        try:
            # 选择对应的api
            if 'gpt' in model:
                ans = chat_once_openai(messages = messages, model = model)
            if chat_type == 'heading_level':
                try:
                    ans = json.loads(ans)
                    return ans
                except:
                    print(f"{chat_type}_{model}:api返回格式错误!")
            else:
                return ans
        except Exception as e:
            print(e)
        retry_time -= 1
    raise Exception(f"{chat_type}_{model}:No useful api keys left!")

def clean_cache():
    """
    清理模型cuda缓存， 但保留模型本身
    :return: None
    """
    torch.cuda.empty_cache()

def slice_text(text, slice_length, overlap_length):
    """
    将文本切片
    :param text: 文本
    :param slice_length: 切片长度
    :param overlap_length: 重叠长度
    :return: 切片列表
    """
    start = 0
    slices = []
    while start < len(text):
        end = start + slice_length
        if end > len(text):
            end = len(text)
        slices.append(text[start:end])
        start += slice_length - overlap_length
    return slices

def symbol_split(text, language = 'ch'):
    """
    根据文本中的特殊符号分割文本
    :param text: 文本
    :param language: 语言
    :return: 分割后的文本列表
    """
    special_symbol = sentense_symbol_chinese if language == 'ch' else sentense_symbol_none_chinese
    sentenses = []
    sentense = ''
    for c in text:
        if c in special_symbol:
            if sentense:
                sentenses.append(sentense + c)
            sentense = ''
        else:
            sentense += c
    if sentense:
        sentenses.append(sentense)
    return sentenses

def get_potential_sentenses(text, language = 'ch', chunk_length = 512):
    paragraphs = [sub for big in text.split('\n\n') for sub in (big.split('\n') if len(big) >= chunk_length else [big])]
    sentenses = []
    for p in paragraphs:
        if len(p) < chunk_length:
            if p.strip() != '':
                sentenses.append(p)
        else:
            for s in symbol_split(p, language):
                if len(s) < chunk_length:
                    if s.strip() != '':
                        sentenses.append(s)
                else:
                    sentenses.extend(slice_text(s, chunk_length, overlap = 0))
    return sentenses

def semantic_split(text, language = 'ch', chunk_length = 512, overlap = 96, threshold = 0.4):
    """
    根据语义分割文本
    :param text: 文本
    :param language: 语言
    :param chunk_length: 切片长度
    :param overlap: 重叠长度
    :param threshold: 语义相似度阈值
    :return: 分割后的文本列表
    """
    sentenses = get_potential_sentenses(text, language, chunk_length)
    embs = emb_model.encode(sentenses)
    embs_score = []
    for i in range(len(embs) - 1):
        embs_score.append(np.dot(embs[i], embs[i + 1]) / (np.linalg.norm(embs[i]) * np.linalg.norm(embs[i + 1])))
    texts = []
    txt_chunk = sentenses[0]
    for i in range(len(embs_score)):
        if len(txt_chunk) + len(sentenses[i]) < chunk_length:
            if embs_score[i] > threshold:
                txt_chunk += sentenses[i]
            else:
                texts.append(txt_chunk)
                txt_chunk = sentenses[i]
        else:
            texts.append(txt_chunk)
            txt_chunk = sentenses[i]
            len_overlap = 0
            for j in range(i - 1, -1, -1):
                if len(txt_chunk) + len(sentenses[j]) < chunk_length and len_overlap < overlap:
                    txt_chunk = sentenses[j] + txt_chunk
                    len_overlap += len(sentenses[j])
                else:
                    break
    if txt_chunk:
        texts.append(txt_chunk)
    return texts

# text = "5.圩区工程背景：1962-1980年，开展了大规模电力排灌建设，初步实现了旱能灌、涝能排、洪能挡的农田水利基本格局；从90年代始，根据社会发展，大力开展圩区整治，改造排灌设施，一大批农田水利工程相继建成。“99·6·30”洪灾后，按照“深挖河、高筑堤、砌护岸、建圩区、控沉降”的治水方针，启动防洪工程建设，初步形成了具有桐乡特色的圩区防洪排涝格局；从2004年起，根据圩区规划，调整圩区格局，开展圩堤、泵站等水利工程标准化建设；2010—2017年，实施浙江省第二批、第五批中央财政小型农田水利建设重点县和中央财政资金小型农田水利项目县建设，防洪排涝能力有了进一步提高。但是，受项目建设覆盖面影响，仍有个别低洼易涝区得不到及时整治，特别是2013年“菲特”台风洪涝灾害，部分没有布置圩区治理的区域淹涝明显，给当地造成了一定的经济损失；此外，随着经济社会的快速发展，农业现代化、城乡一体化进程加快，农业产业结构的调整，对圩区建设提出了新的更高要求，圩区的保护对象也由原来的农田为主扩展至城镇、乡村、工业园区、中心村、经济作物种植区等。从近年来流域治水理念来看，主要围绕建设“杭嘉湖排水”高速公路的思路，以拓宽主要行洪干道，抬高河道水位，将洪水迅速外排出海，在这样一个理念的指导下，流域内各地规划建设的水利工程设防标准明显提高。同时，浙江省杭嘉湖防洪规划仍把杭嘉湖平原作为洪水过境走廊和洪水调蓄区，桐乡必须承接上游来水。另外，省际间、县市间相邻地方在流域治理方面，未按照相关规定，均从本地出发，实施了超出规范标准范围内的相关工程建设，建成了一大批高标准圩区工程，造成流域内容蓄水面积大幅减少。同时，受太湖支流相关河道节制闸建设，致使北排调蓄能力减弱，桐乡在汛期高水位行洪将是常态，洪涝灾害威胁日益加剧。"
# semantic_split(text, language='ch', chunk_length=512, overlap=96, threshold=0.4)

def is_table_exist(img):
    """
    判断图片中是否存在表格
    :param img: 图片
    :return: 是否存在表格
    """
    # 二值化
    _, img_bin = cv2.threshold(img, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

    # 反转图像
    img_bin = 255 - img_bin

    # 定义一个椭圆核
    kernel_length = np.array(img).shape[1] // 80
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * kernel_length, 2 * kernel_length))

    # 执行膨胀和侵蚀
    img_temp1 = cv2.erode(img_bin, kernel, iterations=3)
    img_temp2 = cv2.dilate(img_temp1, kernel, iterations=3)
    img_edges = cv2.subtract(img_bin, img_temp2)

    # 查找轮廓
    contours, _ = cv2.findContours(img_edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    # 判断是否存在表格
    count = 0
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        # 如果存在一个足够大的矩形，那么我们认为存在表格
        if w > 50 and h > 50:
            count += 1

    # 如果找到的矩形数量超过5个，我们认为存在表格
    return count > 5

def doc2docx(self, path):
    w = win32com.client.Dispatch('Word.Application')
    path = os.path.abspath(path)# doc路径
    doc = w.Documents.Open(path)
    # 这里必须要绝对地址,保持和doc路径一致
    newpath = path.replace('.doc','.docx')
    # time.sleep(1)# 暂停3s，否则会出现-2147352567,错误
    doc.SaveAs(newpath, 12, False, "", True, "", False, False, False, False)# 转化后路径下的文件
    doc.Close() #开启则会删掉原来的doc
    w.Quit()# 退出
    os.remove(path)# 删除原来的文件
    return newpath

def is_float(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

def special_symbol_last_remove(text):
    while text[-1] in special_symbol:
        text = text[:-1]
    return text

def letter_to_number(letter):
    if 'a' <= letter <= 'z':
        return 'letter_lower', ord(letter.lower()) - 96
    return 'letter_upper', ord(letter.lower()) - 96

def chinese_to_arabic(chinese):
    chinese_arabic_map = {
        '零': '0',
        '〇': '0',
        '一': '1',
        '二': '2',
        '三': '3',
        '四': '4',
        '五': '5',
        '六': '6',
        '七': '7',
        '八': '8',
        '九': '9',
        '十': '10'
    }
    for key in chinese_arabic_map:
        chinese = chinese.replace(key, chinese_arabic_map[key])
    return chinese

def numbered_headings(text):
    passible = re.finditer(r'(第[\d]+[章节]\s*[^:：——；;\n、$，]|第[零〇一二三四五六七八九十]+[章节]\s*[^:：——；;\n、$，]|[\(（ \t^]*[零〇一二三四五六七八九十]+\s*[、\.）\)]+\s*[^:：——；;\n、$，]*|[\(（ \t^]*[\d]+\s*[、\.\)）]+\s*[^:：——；;\n、$]*|[\(（ \t^]*[a-zA-Z]+\s*[\.\)]+\s*[^:：——；;\n、$]*|[#]+.*)[$:：——:;\n]', text)
    final = []
    pattern = r'''
    (?P<type>
        第
        (?P<number>[\d]+|[零〇一二三四五六七八九十]+)
         (?P<separator>[章节条])
        \s*
        [^:：——；;\n、$，]*
    )
    |
    (
        [\(\（ \t^]*
        (?P<number_2>[零〇一二三四五六七八九十\d]+|[a-zA-Z]+)
        \s*
        (?P<separator>[、\.）\)]?)
        \s*
        [^:：——；;\n、$，a-zA-Z\d]*
    )
    |
    (?P<other>[#]*.*)
    [$:：——:;\n]
    '''
    for item in passible:
        text = special_symbol_last_remove(item.group())
        
        if all(j not in text for j in special_symbol) and not str.isalnum(text) and not is_float(text) and len(text) > 1:
            match = re.match(pattern, text, re.VERBOSE)
            if match:
                details = match.groupdict()
                number = details['number']
                number_type = details['type']
                if re.match(r'[零〇一二三四五六七八九十]+', number):
                    style = 'chinese'
                    if number_type == '第':
                        style += '_chapter'
                    number = [int(chinese_to_arabic(number))]
                elif re.match(r'\d+', number):
                    style = 'arabic'
                    if number_type == '第':
                        style += '_chapter'
                        number = [int(number)]
                    else:
                        combined = re.findall(r'[\d]+[\d\.]+', text)
                        if combined:
                            number = [int(num) for num in combined[0].split('.') if num != '']
                            style += '_combined'
                        else:
                            number = [int(number)]
                elif re.match(r'[a-zA-Z]+', number):
                    style, number = letter_to_number(str(number)[0])
                    number = [number]
                else:
                    style = 'none'
                    number = [-1]
            final.append({
                'text': text,
                'start': item.start(),
                'end': item.end(),
                'number': number,
                'style' : style,
                'separator': details['separator'] if 'separator' in details else ''
            })
    return final

def judge_eng(text):
    def is_special(char: str) -> bool:
        """判断是否为特殊字符"""
        return char in ['。', '，', '；', '！', '？', '、', '：', '“', '”', '‘', '’', '《', '》', '（', '）', '【', '】', '—', '…', '·', '「', '」', '『', '』', '〈', '〉', '﹁', '﹂', '﹃', '﹄', '﹏', '﹐', '﹑', '﹒', '﹔', '﹕', '﹖', '﹗', '﹘', '﹙', '﹚', '﹛', '﹜', '﹝', '﹞', '﹟', '﹠', '﹡', '﹢', '﹣', '﹤', '﹥', '﹦', '﹨', '﹩', '﹪', '﹫', '！', '？', '｡', '。', '､', '、', '，', '；', '：']
    
    def is_chinese(char: str) -> str:
        """判断是否为中文"""
        return '\u4e00' <= char <= '\u9fff'
    cnt_chinese = 0
    cnt_none_chinese = 0
    for char in text:
        if is_special(char):
            continue
        if is_chinese(char):
            cnt_chinese += 1
        else:
            cnt_none_chinese += 1
    if cnt_chinese > cnt_none_chinese:
        return 'ch'
    else:
        return 'none'

def add_section(section, texts, headings, file_name, file_type, chunk_size_limit=512, overlap=96, language='ch', info_type='txt', table_one_line = True) -> list:
    """
    添加一个章节的文本到文本列表
    :param section: 章节文本
    :param texts: 文本列表
    :param headings: 标题列表
    :param file_name: 文件名
    :param file_type: 文件类型
    :param chunk_size_limit: 切片长度
    :param overlap: 重叠长度
    :param language: 语言
    :return: list
    """
    headings_of_section_upper = []
    headings_of_section_lower = numbered_headings(section + '\n') if info_type == 'txt' else []
    if len(section) < chunk_size_limit:
        chunk_id = f'{uuid4().hex}_chunk'
        
    if len(headings) > 0:
        current_heading = headings[-1]
        level = current_heading['level']
        headings_of_section_upper.append(current_heading)
        for i in range((len(headings) - 1), -1, -1):
            if headings[i]['level'] < level:
                headings_of_section_upper.append(headings[i])
                level = headings[i]['level']
    headings_of_section_upper = headings_of_section_upper[::-1]
    if info_type == 'table': 
        sentenses = [p for p in section.split('\n\n') if p.strip() != ''] if table_one_line else get_potential_sentenses(section, language, chunk_size_limit)
        for s in sentenses:
            texts.append({
                "content":s,
                "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "file_name": file_name,
                "file_type": file_type,
                "chunk_id": f'{uuid4().hex}_chunk',
                "chunk_size": len(s),
                "headings": headings_of_section_upper,
                "parent": "",
                "child":[],
                "other meta": {
                    "is_table": True,
                    "is_image": False,
                    "table_info": section,
                    "image_info": False
                }
            })
        return texts
    child = []
    add_already = False
    if len(headings_of_section_lower) > 0:
        add_already = True
        for i in range(len(headings_of_section_lower)):
            start = headings_of_section_lower[i]['end']
            end = headings_of_section_lower[i + 1]['start']if i + 1 < len(headings_of_section_lower) else len(section)
            block = section[start:end]
            if len(block) > chunk_size_limit:
                chunks = semantic_split(block, language, chunk_size_limit, overlap)
                for chunk in chunks:
                    lil_chunk_id = f'{uuid4().hex}_chunk'
                    child.append(lil_chunk_id)
                    headings_chunk = headings_of_section_upper.copy()
                    if headings_chunk:
                        # 提取标题类型，可能是1）或者1.或者1、或是一、等等
                        flag = False
                        for j in range(len(headings_chunk) - 1, -1, -1):
                            if headings_chunk[j]['style'] == headings_of_section_lower[i]['style'] and headings_chunk[j]['separator'] == headings_of_section_lower[i]['separator'] and headings_chunk[j]['number'][-1] == headings_of_section_lower[i]['number'][-1] - 1:
                                if headings_chunk[j]['style'] == 'arabic_combined':
                                    if len(headings_chunk[j]['number']) != len(headings_of_section_lower[i]['number']) or any(headings_chunk[j]['number'][k] != headings_of_section_lower[i]['number'][k]  for k in range(len(headings_chunk[j]['number'] - 1))):
                                        continue
                                level = headings_chunk[j]['level']
                                flag = True
                                break
                        if not flag:
                            level = headings_chunk[-1]['level'] + 1
                    else:
                        level = 1
                    headings_chunk.append({
                        "text": headings_of_section_lower[i]['text'],
                        "level": level,
                        "style": headings_of_section_lower[i]['style'],
                        "number": headings_of_section_lower[i]['number'],
                        "separator": headings_of_section_lower[i]['separator']
                    })
                    texts.append({
                        "content":chunk,
                        "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "file_name": file_name,
                        "file_type": file_type,
                        "chunk_id": lil_chunk_id,
                        "chunk_size": len(chunk),
                        "headings": headings_chunk,
                        "parent": "",
                        "child":[],
                        "other meta": {
                            "is_table": False,
                            "is_image": False,
                            "table_info": None if info_type != 'table' else True,
                            "image_info": None if info_type != 'image' else True
                        }
                    })
            else:
                lil_chunk_id = f'{uuid4().hex}_chunk'
                headings_chunk = headings_of_section_upper.copy()
                if headings_chunk:
                    # 提取标题类型，可能是1）或者1.或者1、或是一、等等
                    flag = False
                    for j in range(len(headings_chunk) - 1, -1, -1):
                        if headings_chunk[j]['style'] == headings_of_section_lower[i]['style'] and headings_chunk[j]['separator'] == headings_of_section_lower[i]['separator'] and headings_chunk[j]['number'][-1] == headings_of_section_lower[i]['number'][-1] - 1:
                            level = headings_chunk[j]['level']
                            flag = True
                            break
                    if not flag:
                        level = headings_chunk[-1]['level'] + 1
                else:
                    level = 1
                headings_chunk.append({
                    "text": headings_of_section_lower[i]['text'],
                    "level": level,
                    "style": headings_of_section_lower[i]['style'],
                    "number": headings_of_section_lower[i]['number'],
                    "separator": headings_of_section_lower[i]['separator']
                })
                texts.append({
                    "content":block,
                    "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "file_name": file_name,
                    "file_type": file_type,
                    "chunk_id": lil_chunk_id,
                    "chunk_size": len(block),
                    "headings": headings_chunk,
                    "parent": "",
                    "child":[],
                    "other meta": {
                        "is_table": False,
                        "is_image": False,
                        "table_info": None,
                        "image_info": None
                    }
                })
    if len(section) < chunk_size_limit:
        texts.append({
            "content":section,
            "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "file_name": file_name,
            "file_type": file_type,
            "chunk_id": chunk_id,
            "chunk_size": len(section),
            "headings": headings_of_section_upper,
            "parent": "",
            "child":child,
            "other meta":{
                "is_table": False,
                "is_image": False,
                "table_info": None if info_type != 'table' else True,
                "image_info": None if info_type != 'image' else True
            }
        })
    elif add_already == False:
        chunks = semantic_split(section, language, chunk_size_limit, overlap)
        for chunk in chunks:
            lil_chunk_id = f'{uuid4().hex}_chunk'
            child.append(lil_chunk_id)
            headings_chunk = headings_of_section_upper.copy()
            texts.append({
                "content":chunk,
                "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "file_name": file_name,
                "file_type": file_type,
                "chunk_id": lil_chunk_id,
                "chunk_size": len(chunk),
                "headings": headings_chunk,
                "parent": "",
                "child":[],
                "other meta": {
                    "is_table": False,
                    "is_image": False,
                    "table_info": None,
                    "image_info": None
                }
            })

    return texts

class DocAnalyze:
    def __init__(self) -> None:
        self.ocr_paddle = None
    
    # Rest of your code... 
    
    def read_doc(self, file_path, chunk_size=512, overlap=96, table_one_line=True):
        """
        读取 doc 和 docx 文件
        :param file_path: 文件路径
        :return: 文本
        """
        if file_path.endswith('.doc'):
            file_path = self.doc2docx(file_path)
        texts = []
        headings = []
        section = ''
        doc = Document(file_path)
        title = None
        first_line_flag = True
        language = 'ch'
        for element in doc.element.body:
            if element.tag.endswith('}t'):  # 找到文本标签
                if element.text:
                    section += element.text.strip('\n') + '\n'
            # 如果元素是段落
            elif isinstance(element, CT_P):
                try:
                    para = Paragraph(element, doc)
                    if para.text == '':  # 如果段落为空，跳过
                        continue
                    if first_line_flag:
                        language = judge_eng(para.text)
                        title = ''
                        first_line_flag = False
                    extracted_headings = numbered_headings(para.text + '\n')
                    if para.style.name.startswith('Heading') or (len(extracted_headings) == 1 and special_symbol_last_remove(para.text.strip()).startswith(extracted_headings[0]['text'])):
                        if para.style.name.startswith('Heading'):
                            level = int(para.style.name.split(' ')[-1])
                            style = 'Heading'
                            number = [-1]
                            separator = 'none'
                        else:
                            extracted_heading = extracted_headings[0]
                            if headings:
                                # 提取标题类型，可能是1）或者1.或者1、或是一、等等
                                flag = False
                                for i in range(len(headings) - 1, -1, -1):
                                    if headings[i]['style'] == extracted_heading['style'] and headings[i]['separator'] == extracted_heading['separator'] and headings[i]['number'][-1] == extracted_heading['number'][-1] - 1:
                                        level = headings[i]['level']
                                        flag = True
                                        break
                                if not flag:
                                    level = headings[-1]['level'] + 1
                            else:
                                level = 1
                            style = extracted_heading['style']
                            separator = extracted_heading['separator']
                            number = extracted_heading['number']
                        headings.append({
                            'text': extracted_heading['text'],
                            'level': level,
                            'style': style,
                            'number' : number,
                            'separator' : separator,
                        })
                        if section != '':
                            add_section(section, texts, headings, file_path, 'docx', chunk_size, overlap, language)
                            section = ''
                    elif title == '':
                        if len(para.text) < 20:
                            title = True
                            headings.append({
                                'text': para.text,
                                'level': 0,
                                'style': 'Title',
                                'number' : [-1],
                                'separator' : 'none',
                            })
                        else:
                            title = False
                    else:
                        section += para.text.strip('\n') + '\n'
                except Exception as e:
                    print(e)
                    pass
            # 如果元素是表格
            elif isinstance(element, CT_Tbl):
                if section:
                    add_section(section, texts, headings, file_path, 'docx', chunk_size, overlap, language)
                    section = ''
                # 读取每一个表格的文本
                table = Table(element, doc)
                ceil_set = set()
                first_row = True
                titles_of_table = []
                for row in table.rows:
                    if first_row:
                        for cell in row.cells:
                            titles_of_table.append(cell.text.strip('\n'))
                        first_row = False
                        continue
                    for i, cell in enumerate(row.cells):
                        ceil_set.add(cell)
                        cell_text = cell.text.replace('\n', '')
                        section +=f"{titles_of_table[i]}:{cell_text}\n"
                    section += '\n\n'
                if section:
                    add_section(section, texts, headings, file_path, 'docx', chunk_size, overlap, language, 'table', table_one_line)
                    section = ''
        if section:
            add_section(section, texts, headings, file_path, 'docx', chunk_size, overlap, language)
        return texts,headings

    def read_pdf(self, file_path):
        """
        读取 pdf 文件
        :param file_path: 文件路径
        :return: 文本
        """
        text = ''
        doc = fitz.open(file_path)
        # pdf = PDF(src=file_path)
        # pdf_tables = pdf.extract_tables(ocr=ocr,borderless_tables=False)
        for i, page in enumerate(doc):
            page_text = page.get_text()
            if page_text:  # 如果页面有文本，直接添加
                text += page_text.strip('\n') + '\n\n'
            else:  # 如果页面没有文本，尝试提取图片并使用 OCR
                print('OCR识别')
                if not self.ocr_paddle:
                    self.ocr_paddle = PaddleOCR(use_angle_cls=True, lang='ch')  # need to run only once to download and load model into memory
                for img in doc.get_page_images(i):
                    xref = img[0]
                    img_data = doc.extract_image(xref)
                    img_bytes = img_data['image']

                    # text += img_text
                    image = Image.open(io.BytesIO(img_bytes))
                    img_array = np.array(image)
                    img_text = self.ocr_paddle.ocr(img_array)  # 使用 PaddleOCR 提取图片中的文本

                    for line in img_text:
                        line_text = []
                        for word_info in line:
                            if isinstance(word_info, list) and word_info[-1][0] != ' ':
                                line_text.append(str(word_info[-1][0]))
                            elif isinstance(word_info, str) and word_info != ' ':
                                line_text.append(str(word_info))
                            else:
                                line_text.append(str(word_info))
                        line_text = '\n'.join(line_text)
                        text += line_text.strip('\n') + '\n\n'
        return text

    def read_txt(self, file_path, chunk_size=512, overlap=96):
        """
        读取 txt 或 md 文件
        :param file_path: 文件路径
        :return: 文本
        """
        texts = []
        headings = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f.readlines():
                    text = line.strip()
                    if text == '':  # 如果段落为空，跳过
                        continue
                    if first_line_flag:
                        language = judge_eng(text)
                        title = ''
                        first_line_flag = False
                    extracted_headings = numbered_headings(text + '\n')
                    if len(extracted_headings) == 1 and extracted_headings[0]['text'] == special_symbol_last_remove(text):
                        extracted_heading = extracted_headings[0]
                        if headings:
                            # 提取标题类型，可能是1）或者1.或者1、或是一、等等
                            flag = False
                            for i in range(len(headings) - 1, -1, -1):
                                if headings[i]['style'] == extracted_heading['style'] and headings[i]['separator'] == extracted_heading['separator'] and headings[i]['number'] == extracted_heading['number'] - 1:
                                    level = headings[i]['level']
                                    flag = True
                                    break
                            if not flag:
                                level = headings[-1]['level'] + 1
                        else:
                            level = 1
                        number = extracted_heading['number']
                        style = extracted_heading['style']
                        separator = extracted_heading['separator']
                        if section != '':
                            add_section(section, texts, headings, file_path, 'docx', chunk_size, overlap, language)
                            section = ''
                        headings.append({
                            'text': special_symbol_last_remove(text),
                            'level': level,
                            'style': style,
                            'number' : number,
                            'separator' : separator,
                        })
                    elif title == '':
                        if len(text) < 20:
                            title = True
                            headings.append({
                                'text': text,
                                'level': 0,
                                'style': 'Title',
                                'number' : [-1],
                                'separator' : 'none',
                            })
                        else:
                            title = False
                    else:
                        section += text.strip('\n') + '\n'
            if section:
                add_section(section, texts, headings, file_path, 'docx', chunk_size, overlap, language)
        except Exception as e:
            print(e)
            pass
        return texts


    def analyze_doc(self, file, chunk_size=512, overlap=96, table_one_line=True):
        """
        分析文档
        :param path: 文档路径
        :return: None
        """
        print(file)
        texts = []
        headings = []
        file_path = file
        file_name = os.path.basename(file_path)
        file_type = file_name.split('.')[-1]
        try:
            if file_type == 'pdf':
                texts = self.read_pdf(file_path)
            elif file_type == 'doc' or file_type == 'docx':
                texts, headings = self.read_doc(file_path, chunk_size, overlap, table_one_line)
            elif file_type == 'txt' or file_type == 'md':
                texts, headings = self.read_txt(file_path, chunk_size, overlap)
        except Exception as e:
            print(e)
        return texts, headings

if __name__ == '__main__':
    # print(numbered_headings('1. 测试\nsahdoihaoidso\n（2)sdhoi\n'))
    # print(numbered_headings('一、基本情况\n'))
    # print(numbered_headings('a)基本情况\n'))
    # print(numbered_headings('1、火灾现场处置方案\n'))

    time = datetime.now()
    doc_analyze = DocAnalyze()
    chunks,headings = doc_analyze.analyze_doc(r'..\data\01塘南圩区.docx')
    used_time = datetime.now() - time
    print(used_time)
    with open('../data/chunks.json', 'w', encoding='utf-8') as f:
        json.dump(chunks, f, ensure_ascii=False, indent=4)
    with open('../data/headings.json', 'w', encoding='utf-8') as f:
        json.dump(headings, f, ensure_ascii=False, indent=4)