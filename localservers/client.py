from mcp.server.fastmcp import FastMCP
from config import DB_CONFIG
import pymysql
import utils

# 初始化mcp服务
mcp = FastMCP("mysql-mcp")

@mcp.tool()
def list_tables():
    """
    获取数据库所有表名
    """
    try:
        mydb = pymysql.connect(**DB_CONFIG)
        mycursor = mydb.cursor()
        mycursor.execute("SHOW TABLES")
        tables = mycursor.fetchall()
        table_names = [table[0] for table in tables]
        return table_names
    except pymysql.Error as err:
        print(f"MySQL Error: {err}")
        return {"error": str(err)}
    finally:
        if 'mycursor' in locals():
            mycursor.close()
        if 'mydb' in locals():
            mydb.close()

@mcp.tool()
def describ_table(table_name:str):
    """
       返回表的结构
       """
    try:
        mydb = pymysql.connect(**DB_CONFIG)
        mycursor = mydb.cursor()
        mycursor.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = %s",table_name)
        table_desc = mycursor.fetchall()
        return table_desc
    except pymysql.Error as err:
        print(f"MySQL Error: {err}")
        return {"error": str(err)}
    finally:
        if 'mycursor' in locals():
            mycursor.close()
        if 'mydb' in locals():
            mydb.close()

@mcp.tool()
def execute_sql(sql:str):
    """
    执行SQL语句,返回查询结果
    """
    try:
        mydb = pymysql.connect(**DB_CONFIG)
        mycursor = mydb.cursor()
        mycursor.execute(sql)
        # 获取列名
        column_names = [desc[0] for desc in mycursor.description]
        if mycursor.rowcount == 0:
            mydb.commit()
            return {"message": "执行成功，无返回结果"}
        else:
            return utils.data_transformer(column_names,mycursor.fetchall())
    except pymysql.Error as err:
        print(f"MySQL Error: {err}")
        return {"error": str(err)}
    finally:
        if 'mycursor' in locals():
            mycursor.close()
        if 'mydb' in locals():
            mydb.close()



if __name__ == "__main__":
    print("启动mysql-mcp服务")
    mcp.run(transport="stdio")

