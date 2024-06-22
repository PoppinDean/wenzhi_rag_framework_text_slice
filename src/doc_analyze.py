'''
Author: Dean
Date: 2023-11-18 21:03:56
LastEditTime: 2023-12-09 18:00:04
LastEditors: your name
Description: 
FilePath: \python\machine_learning\multi_chat\multi_doc_to_emb.py
可以输入预定的版权声明、个性签名、空行等
'''
from datetime import datetime
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
from docx import Document
from docx.oxml.table import CT_Tbl
from docx.table import _Cell, Table
from docx.oxml.text.paragraph import CT_P
from docx.text.paragraph import Paragraph
import win32com.client
import tabula
import pdfplumber
# from chinese_splitter import ChineseRecursiveTextSplitter
from splitter_overlap import RecursiveTextSplitter

special_symbol = ['\n', '\r', '!', '@', '#', '$', '%', '^', '&', '*', '_', '+', '=', '`', '~', '[', ']', '{', '}', '\\', '|', ';', ':', ',', '<',  '>', '/', '?', '！', '￥', '…', '—', '【', '】', '：', '，', '。', '？', '～']

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

def numbered_headings(text):
    passible = re.findall(r'([\(|（| |\t|^]*[ 零〇一二三四五六七八九十]+\s*[、\.）\)][^:：——；;\n、$，a-zA-Z\d]*|[\d]+\s*[\.\)][^:：——；;\n、$a-zA-Z]*|[a-zA-Z]+\s*[\.\)][^:：——；;\n、$]*)', text)
    
    final = [item for item in passible if all(j not in item for j in special_symbol) and not str.isalnum(item) and not is_float(item) and len(item) > 1]
    return final

class DocAnalyze:
    def __init__(self) -> None:
        self.ocr_paddle = None
    
    # Rest of your code...

    def read_doc(self, file_path):
        """
        读取 doc 和 docx 文件
        :param file_path: 文件路径
        :return: 文本
        """
        if file_path.endswith('.doc'):
            file_path = self.doc2docx(file_path)
        text = ''
        section = ''
        doc = Document(file_path)
        for element in doc.element.body:
            if element.tag.endswith('}t'):  # 找到文本标签
                if element.text:
                    section += element.text.strip('\n') + '\n'
            # 如果元素是段落
            elif isinstance(element, CT_P):
                try:
                    para = Paragraph(element, doc)
                    if para.style.name.startswith('Heading') or numbered_headings(para.text):
                        if section != '':
                            text += section.strip('\n') + '\n\n'
                            section = ''
                    section += para.text.strip('\n') + '\n'
                except:
                    pass
            # 如果元素是表格
            elif isinstance(element, CT_Tbl):
                if section:
                    text += section.strip('\n') + '\n\n'
                    section = ''
                # 读取每一个表格的文本
                table = Table(element, doc)
                ceil_set = set()
                for row in table.rows:
                    for cell in row.cells:
                        if cell in ceil_set:
                            continue
                        ceil_set.add(cell)
                        text += cell.text.strip('\n') + ','
                    text += '\n'
                text += '\n\n'
        if section:
            text += section.strip('\n') + '\n\n'
        return text

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

    def read_txt(self, file_path):
        """
        读取 txt 或 md 文件
        :param file_path: 文件路径
        :return: 文本
        """
        text = ''
        with open(file_path, 'r', encoding='utf-8') as f:
            text += f.read()
        return text


    def analyze_doc(self, file):
        """
        分析文档
        :param path: 文档路径
        :return: None
        """
        chunk_splitter = RecursiveTextSplitter(
            keep_separator=True,
            is_separator_regex=True,
            chunk_size=512,
            chunk_overlap=96
        )

        print(file)
        text = ""
        file_path = file
        file_name = os.path.basename(file_path)
        file_type = file_name.split('.')[-1]
        try:
            if file_type == 'pdf':
                text = self.read_pdf(file_path)
            elif file_type == 'doc' or file_type == 'docx':
                text = self.read_doc(file_path)
            elif file_type == 'txt' or file_type == 'md':
                text = self.read_txt(file_path)
        except Exception as e:
            print(e)
        # seperate_overlap

        chunks = chunk_splitter.split_text(text)
        chunks_info = []
        for chunk in chunks:
            chunk_id = f'{uuid4().hex}_chunk'
            chunks_info.append(
                {
                    "content":chunk,
                    "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "file_name": file_name,
                    "file_type": file_type,
                    "chunk_id": chunk_id,
                    "chunk_size": len(chunk),
                    "headings":numbered_headings(chunk),
                    "parent": "",
                    "child":[],
                    "other meta":{
                        "is_table": False,
                        "is_image": False,
                        "table_info": None,
                        "image_info": None
                    }
                }
            )
        return chunks_info

if __name__ == '__main__':
    doc_analyze = DocAnalyze()
    chunks = doc_analyze.analyze_docs(r'D:\Allcode\python\machine_learning\multi_chat\docs')
    print(chunks)