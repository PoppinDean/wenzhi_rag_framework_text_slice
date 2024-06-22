import requests

def create_database(url, name):
    url = url + '/createDB'
    data = {
        'name': name
    }
    res = requests.post(url, json=data)
    res_json = res.json()
    if res_json['code'] != 200:
        print(res_json['msg'])
        return None
    print('创建数据库请求成功')
    return res_json['result']

def get_db_name(url, db_id):
    url = url + '/getDBName'
    data = {
        'db_id': db_id
    }
    res = requests.get(url, json=data)
    res_json = res.json()
    if res_json['code'] != 200:
        print(res_json['msg'])
        return None
    print('获取数据库名请求成功')
    return res_json['result']

def import_files(url, db_id, file_paths):
    url = url + '/importFiles'
    data = {
        'db_id': db_id,
        'file_paths': file_paths
    }
    res = requests.post(url, json=data)
    res_json = res.json()
    if res_json['code'] != 200:
        print(res_json['msg'])
        return None
    print('添加文件请求成功')
    return res_json['result']

def get_files(url, db_id):
    url = url + '/getFiles'
    data = {
        'db_id': db_id
    }
    res = requests.get(url, json=data)
    res_json = res.json()
    if res_json['code'] != 200:
        print(res_json['msg'])
        return None
    print('获取文件请求成功')
    return res_json['result']

def delete_files(url, db_id, files):
    url = url + '/deleteFiles'
    data = {
        'db_id': db_id,
        'files': files
    }
    res = requests.post(url, json=data)
    res_json = res.json()
    if res_json['code'] != 200:
        print(res_json['msg'])
        return None
    print('删除文件请求成功')
    return res_json['result']

def delete_db(url, db_id):
    url = url + '/deleteDB'
    data = {
        'db_id': db_id
    }
    res = requests.post(url, json=data)
    res_json = res.json()
    if res_json['code'] != 200:
        print(res_json['msg'])
        return None
    print('删除数据库请求成功')
    return res_json['result']

def check_db(url, db_id):
    url = url + '/checkDB'
    data = {
        'db_id': db_id
    }
    res = requests.get(url, json=data)
    res_json = res.json()
    if res_json['code'] != 200:
        print(res_json['msg'])
        return None
    print('检查数据库请求成功')
    return res_json['result']

def search_db(url, db_id, query, top_k =[5], threshold=0.6, reranker=False, keywords=[], key_search_type='none'):
    url = url + '/search'
    data = {
        'db_id': db_id,
        'query': query,
        'top_k': top_k,
        'threshold': threshold,
        'reranker': reranker,
        'keywords': keywords,
        'key_search_type': key_search_type
    }
    res = requests.get(url, json=data)
    res_json = res.json()
    if res_json['code'] != 200:
        print(res_json['msg'])
        return None
    print('搜索数据库请求成功')
    return res_json['result']

if __name__ == '__main__':
    url = 'http://10.7.115.165:8888'
    # db_id = create_database(url, 'test')
    # print('数据库id:', db_id)
    # print('检测数据库:',check_db(url, db_id))
    # print('数据库名:', get_db_name(url, db_id))
    # print('添加文件:', import_files(url, db_id, ['./data/test.txt']))
    # print('获取文件:', get_files(url, db_id))
    # print('搜索数据库:', search_db(url, db_id, '测试一下呢'))
    # print('删除数据库:', delete_db(url, db_id))
    # print('检测数据库:',check_db(url, db_id))
    db_id = create_database(url, '水利test')
    print('数据库id:', db_id)
    print('检测数据库:',check_db(url, db_id))
    print('数据库名:', get_db_name(url, db_id))
    print('添加文件:', import_files(url, db_id, ['./data/01塘南圩区.docx', './data/桐乡市东浜头圩区控制运行计划-.docx']))
    print('获取文件:', get_files(url, db_id))
    # db_id = "fbcd5a570d554f5c9a851be23d0dedcb"
    print('搜索数据库:', search_db(url, db_id, '塘南圩区的运行调度原则是什么？', keywords=['控制运行计划'],  ---key_search_type='any'))
    print('删除文件:', delete_files(url, db_id, ['桐乡市东浜头圩区控制运行计划-.docx']))
    print('获取文件:', get_files(url, db_id))
    print('搜索数据库:', search_db(url, db_id, '塘南圩区的运行调度原则是什么？', keywords=['控制运行计划'], key_search_type='any'))
    print('删除数据库:', delete_db(url, db_id))