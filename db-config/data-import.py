import pandas as pd
import pymysql
import json

# 数据库连接配置
DB_CONFIG = {
    'host': '192.168.1.101',  # 数据库主机地址
    'port': 3380,  # 数据库端口
    'user': 'root',  # 您的MySQL用户名
    'password': 'bufan12345.',  # 您的MySQL密码
    'database': 'products_db',  # 您的数据库名称
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

# CSV文件路径
CSV_FILE_PATH = '热成像产品手册_数据.csv'

# 数据库表名
TABLE_NAME = 'products'

def import_csv_to_mysql(csv_file, db_config, table_name):
    """
    将CSV文件数据导入到MySQL数据库中。
    """
    try:
        # 读取CSV文件
        # 假设CSV文件第一行是表头，并且列名与数据库表字段对应
        df = pd.read_csv(csv_file, encoding='gbk')
        print(f"成功读取CSV文件: {csv_file}")
        print("CSV文件前5行数据:")
        print(df.head())

        # 建立数据库连接
        connection = pymysql.connect(**db_config)
        print("成功连接到MySQL数据库。")

        try:
            with connection.cursor() as cursor:
                # 遍历DataFrame的每一行，将数据插入到数据库
                for index, row in df.iterrows():
                    # 映射CSV列名到数据库字段名
                    # 请根据您的CSV文件实际列名进行调整
                    product_line = row.get('产品线名称', row.get('产品线', '')) # 假设CSV中可能的产品线名称列
                    category = row.get('产品品类', row.get('品类', '')) # 假设CSV中可能的产品品类列
                    model = row.get('型号', '')
                    features = row.get('特点', '')
                    application_scenarios = row.get('应用场景', '')
                    
                    # '参数' 列是JSON格式，需要特殊处理
                    parameters_str = row.get('参数', '{}')
                    try:
                        parameters = json.dumps(json.loads(parameters_str), ensure_ascii=False)
                    except json.JSONDecodeError:
                        print(f"警告: '参数' 列数据格式不正确，跳过此行或使用空JSON: {parameters_str}")
                        parameters = json.dumps({}) # 如果JSON解析失败，使用空JSON

                    # SQL插入语句，使用INSERT ... ON DUPLICATE KEY UPDATE 来处理重复的 product_line 和 model
                    # 如果 product_line 和 model 组合已存在，则更新 features, application_scenarios, parameters
                    sql = f"""
                    INSERT INTO {table_name} (product_line, category, model, features, application_scenarios, parameters)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        category = VALUES(category),
                        features = VALUES(features),
                        application_scenarios = VALUES(application_scenarios),
                        parameters = VALUES(parameters);
                    """
                    cursor.execute(sql, (product_line, category, model, features, application_scenarios, parameters))
                
                # 提交事务
                connection.commit()
                print(f"所有数据已成功导入到表 '{table_name}'。")

        finally:
            connection.close()
            print("MySQL数据库连接已关闭。")

    except FileNotFoundError:
        print(f"错误: 找不到CSV文件 '{csv_file}'。请检查文件路径。")
    except pd.errors.EmptyDataError:
        print(f"错误: CSV文件 '{csv_file}' 为空。")
    except pymysql.Error as e:
        print(f"MySQL数据库操作错误: {e}")
    except Exception as e:
        print(f"发生未知错误: {e}")

if __name__ == "__main__":
    # 在运行脚本前，请务必修改 DB_CONFIG 中的数据库连接信息
    # 并且确保 '热成像产品手册_数据.csv' 文件在脚本的同一目录下，或者提供完整路径
    import_csv_to_mysql(CSV_FILE_PATH, DB_CONFIG, TABLE_NAME)
