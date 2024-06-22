import json
import os
import pickle
import numpy as np
import shutil
from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import normalize
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from uuid import uuid4
from doc_analyze import DocAnalyze


class Database:
    def __init__(self, path:str = '') -> None:
        """
        初始化
        :param path: str 包含所有数据库信息的文件的存储路径
        """
        
        if path == '':
            self.current_path = os.path.dirname(__file__)
            path = os.path.join(self.current_path, 'dbs_id.json')
        else:
            self.current_path = os.path.dirname(path)
        self.dbs = json.load(open(path, 'r', encoding='utf-8')) if os.path.exists(path) else {}
        self.db_id = None
        self.loaded = False
        self.emb_model = None
        self.reranker = None
        self.doc_analyze = None
        self.chunks = []
        self.embeddings = None
  
    
    def load_reranker(self, model_path:str = '') -> bool:
        """
        加载reranker模型
        :param model_path: str 模型路径
        :return: bool 是否加载成功
        """
        if model_path == '':
            model_path = os.path.join(self.current_path, 'model/bge-reranker')
        if not os.path.exists(model_path):
            return False
        self.reranker = AutoModelForSequenceClassification.from_pretrained(model_path).to('cuda') if torch.cuda.is_available() else AutoModelForSequenceClassification.from_pretrained(model_path)
        self.reranker.eval()
        return True
    
    
    def load_model(self, model_path:str = "") -> bool:
        """
        加载向量模型
        :param model_path: str 模型路径
        :return: bool 是否加载成功
        """
        if model_path == '':
            model_path = os.path.join(self.current_path, 'model/tao-8k')
        if not os.path.exists(model_path):
            return False
        self.emb_model =  SentenceTransformer(model_path).to('cuda') if torch.cuda.is_available() else SentenceTransformer(model_path)

    def get_db_name(self, db_id:str) -> dict:
        """
        获取数据库名称
        :param db_id: str 数据库id
        :return: dict 返回数据库名称
        """
        if db_id in self.dbs:
            return {
                'status': 'success',
                'name': self.dbs[db_id]['name']
            }
        return {
            'status': 'no such id',
            'name': None
        }
    
    def get_files(self, db_id:str) -> dict:
        """
        获取数据库文件
        :param db_id: str 数据库id
        :return: dict 返回文件列表
        """
        if db_id in self.dbs:
            return {
                'status': 'success',
                'files': self.dbs[db_id]['files']
            }
        return {
            'status': 'no such id',
            'files': None
        }
    
    def check_db(self, db_id:str) -> bool:
        """
        检查数据库是否存在
        :param db_id: str 数据库id
        :return: bool 是否存在
        """
        return db_id in self.dbs
    
    def create_db(self, name:str) -> str:
        """
        创建数据库
        :param name: str 数据库名称
        :return: str 数据库id
        """
        db_id = f'{uuid4().hex}'
        self.dbs[db_id] = {
            'name': name,
            'path': os.path.join(self.current_path, 'database', 'dbs', db_id),
            'files': []
        }
        os.mkdir(self.dbs[db_id]['path'])
        with open(os.path.join(self.current_path, 'database', 'dbs_id.json'), 'w', encoding='utf-8') as f:
            json.dump(self.dbs, f, ensure_ascii=False, indent=4)
        self.db_info = self.dbs[db_id]
        self.loaded = True
        self.save_db()
        return db_id
    
    def load_db(self, db_id:str) -> bool:
        """
        加载数据库
        :param db_id: str 数据库id
        :return: bool 是否加载成功
        """
        if db_id in self.dbs:
            self.db_info = self.dbs[db_id]
            self.chunks = json.load(open(os.path.join(self.db_info['path'], 'chunks.json'), 'r', encoding='utf-8')) if os.path.exists(self.db_info['path']) else []
            self.embeddings = pickle.load(open(os.path.join(self.db_info['path'], 'embeddings.pkl'), 'r', encoding='utf-8')) if os.path.exists(self.db_info['path']) else None
            self.loaded = True
            return True
        self.loaded = False
        return False
    
    def delete_db(self, id:str) -> bool:
        """
        删除数据库
        :param id: str 数据库id
        :return: bool 是否删除成功
        """
        if id in self.dbs:
            path = self.dbs[id]['path']
            if os.path.isdir(path):
                shutil.rmtree(path)
            del self.dbs[id]
            with open(os.path.join(self.current_path, 'database', 'dbs_id.json'), 'w', encoding='utf-8') as f:
                json.dump(self.dbs, f, ensure_ascii=False, indent=4)
            return True
        return False
    
    def save_db(self) -> bool:
        """
        保存数据库
        :return: bool 是否保存成功
        """
        try:
            with open(os.path.join(self.db_info['path'], 'chunks.json'), 'w', encoding='utf-8') as f:
                json.dump(self.chunks, f, ensure_ascii=False, indent=4)
            if self.embeddings is not None:
                with open(os.path.join(self.db_info['path'], 'embeddings.pkl'), 'w', encoding='utf-8') as f:
                    pickle.dump(self.embeddings, f)
            return True
        except:
            return False
    
    def add_files(self, db_id:str, files:list) -> dict:
        """
        向数据库添加文件
        :param files: list 文件列表
        :return: dict 添加结果，包括成功文件和失败文件
        """
        if not self.loaded:
            if not self.load_db(db_id):
                return {
                    'status': 'database not loaded',
                    'success_files': [],
                    'failed_files': files,
                    'files_already_in_db': []
                }
        try:
            if self.doc_analyze is None:
                self.doc_analyze = DocAnalyze()
            success_files = []
            failed_files = []
            files_already_in_db = []
            if self.emb_model is None:
                self.load_model()
            for file in files:
                if not os.path.exists(file):
                    failed_files.append(file)
                    continue
                if os.path.basename(file) in self.db_info['files']:
                    files_already_in_db.append(file)
                    continue
                success_files.append(file)
                chunks_origin = self.doc_analyze.analyze_doc(file)
                # sum = {}
                # propositions = {}
                self.db_info['files'].append(os.path.basename(file))
                self.chunks.extend(chunks_origin)
                chunks_batch = [chunks_origin[i:i+64] for i in range(0, len(chunks_origin), 64)]

                for batch in chunks_batch:
                    embs = self.emb_model.encode(batch, convert_to_numpy=True, normalize_embeddings=True)
                    if self.embeddings is None:
                        self.embeddings = embs
                    else:
                        self.embeddings = np.concatenate([self.embeddings, embs], axis=0)
            with open(os.path.join(self.current_path, 'database', 'dbs_id.json'), 'w', encoding='utf-8') as f:
                json.dump(self.dbs, f, ensure_ascii=False, indent=4)
        except:
            for file in success_files:
                files.remove(file)
            self.save_db()
            return {
                'status': 'failed',
                'success_files': success_files,
                'failed_files': failed_files
            }
        self.save_db()
        return {
            'status': 'success',
            'success_files': success_files,
            'failed_files': failed_files,
            'files_already_in_db': files_already_in_db
        }
        
    
    def delete_files(self, db_id:str, files:list) -> dict:
        """
        删除数据库文件
        :param files: list 文件列表
        :return: dict 删除结果
        """
        if not self.loaded:
            if not self.load_db(db_id):
                return {
                    'status': 'database not loaded',
                    'success_files': [],
                    'failed_files': files
                }
        success_files = []
        failed_files = []
        files_base = [os.path.basename(file) for file in files]
        idxs_to_delete = []
        for file in files_base:
            if file in self.db_info['files']:
                for idx, chunk in enumerate(self.chunks):
                    if chunk['file_name'] == file:
                        idxs_to_delete.append(idx)
                self.db_info['files'].remove(file)
                success_files.append(file)
            else:
                failed_files.append(file)
        self.chunks = [self.chunks[i] for i in range(len(self.chunks)) if i not in idxs_to_delete]
        self.embeddings = np.delete(self.embeddings, idxs_to_delete, axis=0)
        self.save_db()
        with open(os.path.join(self.current_path, 'database', 'dbs_id.json'), 'w', encoding='utf-8') as f:
            json.dump(self.dbs, f, ensure_ascii=False, indent=4)
        return {
            'status': 'success',
            'success_files': success_files,
            'failed_files': failed_files
        }
    
    def search(self, db_id, query:str, top_k:list = [5], threshold:float = 0.6, reranker:bool=False, keywords:list = [], key_search_type:str = 'none') -> dict:
        """
        搜索
        :param query: str 查询语句
        :param top_k: list 返回结果数量
        :param threshold: float 阈值
        :param reranker: bool 是否需要rerank
        :return: list 搜索结果
        """
        if self.loaded == False:
            if not self.load_db(db_id):
                return {
                    'status': 'database not loaded',
                    'result': None
                }
        if reranker == True:
            if len(top_k) != 2:
                return {
                    'status': 'when you need rerank, top_k should be a list with two elements',
                    'result': None
                }
        if self.reranker is None:
            self.load_reranker()
        if self.emb_model is None:
            self.load_model()
        query_emb = normalize(self.emb_model.encode([query], convert_to_numpy= True, normalize_embeddings=True))[0]
        scores = query_emb @ self.embeddings.T
        top_k_info_ids_raw = np.argsort(scores)[::-1][:top_k[0]]
        top_k_info_ids = []
        for info_id in top_k_info_ids_raw:
            if scores[info_id] >= threshold:
                top_k_info_ids.append(info_id)
            else:
                break
        if key_search_type != 'none':
            top_k_info_ids = [info_id for info_id in top_k_info_ids if all(keyword in self.chunks[info_id]['content'] for keyword in keywords)] if key_search_type == 'all' else [info_id for info_id in top_k_info_ids if any(keyword in self.chunks[info_id]['content'] for keyword in keywords)]
        if reranker == False:
            return {
                'status': 'success',
                'result': [self.chunks[info_id] for info_id in top_k_info_ids]
            }
        rerank_scores = []
        for info_id in top_k_info_ids:
            rerank_scores.append(self.rerank_scores(query, self.chunks[info_id]['content']))
        rerank_scores = np.array(rerank_scores)
        rerank_top_k = np.argsort(rerank_scores)[::-1][:top_k[1]]
        return {
            'status': 'success',
            'result': [self.chunks[top_k_info_ids[info_id]] for info_id in rerank_top_k]
        }
    
if __name__ == '__main__':
    db = Database()
    db_id = db.create_db('test')
    print(db_id)
    print(db.add_files(db_id,['../data/test.txt']))
    print(db.search(db_id, '测试一下呢'))
    print(db.delete_db(db_id))
    print('done')