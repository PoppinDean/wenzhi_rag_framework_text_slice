import os
import sys
sys.path.append('.\src')
from src.database import Database
import flask

app = flask.Flask(__name__)
db = Database()

@app.route('/createDB', methods=['POST'])
def create_db():
    """
    创建数据库
    :return: str 数据库id
    """
    try:
        name = flask.request.json['name']
        db_id = db.create_db(name)
        return {
            'code': 200,
            'msg': 'success',
            'result': db_id
        }
    except Exception as e:
        return {
            'code': 400,
            'msg': str(e),
            'result': None
        }
    

@app.route('/getDBName', methods=['GET'])
def get_db_name():
    """
    获取数据库名称
    :return: dict 返回数据库名称
    """
    try:
        db_id = flask.request.json['db_id']
        return {
            'code': 200,
            'msg': 'success',
            'result': db.get_db_name(db_id)
        }
    except Exception as e:
        return {
            'code': 400,
            'msg': str(e),
            'result': None
        }

@app.route('/getFiles', methods=['GET'])
def get_files():
    """
    获取数据库文件
    :return: dict 返回文件列表
    """
    try:
        db_id = flask.request.json['db_id']
        return {
            'code': 200,
            'msg': 'success',
            'result': db.get_files(db_id)
        }
    except Exception as e:
        return {
            'code': 400,
            'msg': str(e),
            'result': None
        }

@app.route('/checkDB', methods=['GET'])
def check_db():
    """
    检查数据库是否存在
    :return: bool 是否存在
    """
    try:
        db_id = flask.request.json['db_id']
        return {
            'code': 200,
            'msg': 'success',
            'result': db.check_db(db_id)
        }
    except Exception as e:
        return {
            'code': 400,
            'msg': str(e),
            'result': None
        }

@app.route('/importFiles', methods=['POST'])
def add_files():
    """
    添加文件
    :return: bool 是否添加成功
    """
    try:
        json_info = flask.request.json
        db_id = json_info['db_id']
        file_paths = json_info['file_paths']
        file_paths_abs = [os.path.abspath(file_path) for file_path in file_paths]
        result = db.add_files(db_id, file_paths_abs)
        faild_files = []
        success_files = []
        for i, file_path_abs in enumerate(file_paths_abs):
            if file_path_abs in result['failed_files']:
                faild_files.append(file_paths[i])
            else:
                success_files.append(file_paths[i])
        result['failed_files'] = faild_files
        result['success_files'] = success_files
        return {
            'code': 200,
            'msg': 'success',
            'result': result
        }
    except Exception as e:
        return {
            'code': 400,
            'msg': str(e),
            'result': None
        }

@app.route('/deleteFiles', methods=['POST'])
def delete_files():
    """
    删除文件
    :return: bool 是否删除成功
    """
    try:
        json_info = flask.request.json
        db_id = json_info['db_id']
        files = json_info['files']
        return {
            'code': 200,
            'msg': 'success',
            'result': db.delete_files(db_id, files)
        }
    except Exception as e:
        return {
            'code': 400,
            'msg': str(e),
            'result': False
        }

@app.route('/deleteDB', methods=['POST'])
def delete_db():
    """
    删除数据库
    :return: bool 是否删除成功
    """
    try:
        db_id = flask.request.json['db_id']
        return {
            'code': 200,
            'msg': 'success',
            'result': db.delete_db(db_id)
        }
    except Exception as e:
        return {
            'code': 400,
            'msg': str(e),
            'result': False
        }

@app.route('/search', methods=['get'])
def search():
    """
    搜索
    :return: list 搜索结果
    """
    try:
        json_info = flask.request.json
        db_id = json_info['db_id']
        query = json_info['query']
        top_k = json_info.get('top_k', [5])
        threshold = json_info.get('threshold', 0.6)
        reranker = json_info.get('reranker', False)
        keywords = json_info.get('keywords', [])
        key_search_type = json_info.get('key_search_type', 'none')
        if key_search_type not in ['none', 'all', 'any']:
            return {
                'code': 400,
                'msg': 'key_search_type must be one of ["none", "all", "any"]',
                'result': None
            }
        return {
            'code': 200,
            'msg': 'success',
            'result': db.search(db_id, query, top_k, threshold, reranker, keywords, key_search_type)
        }
    except Exception as e:
        return {
            'code': 400,
            'msg': str(e),
            'result': None
        }

if __name__ == "__main__":
    app.run(host='0.0.0.0' , port=8888, debug=False)

