from distutils.command.clean import clean
from lib2to3.pgen2.token import VBAR
from os import path

# for auto closing cursors
from contextlib import closing

import sqlite3 as sql


class FlaskMetrics():
    
    def __init__(self,database_name="database.db",max_rows=100,ignore_ips=[]) -> None:
        
        self.max_rows = max_rows
        self.ignore_ips = ignore_ips
        if not path.exists(database_name):
            # init database writer
            self.connector = sql.connect(database_name,check_same_thread=False)
            self.connector.row_factory = sql.Row
            self.__init_db()
            
            
        # init database writer
        self.connector = sql.connect(database_name,check_same_thread=False)
        self.connector.row_factory = sql.Row
        
            
    def __init_db(self) -> None:
        
        with closing(self.connector.cursor()) as cursor:
            
            cursor.execute("CREATE TABLE METRICS (IP_ADDR TEXT,URL TEXT, BROWSER TEXT, ACCEPT_LANGUAGES TEXT, DATE TEXT DEFAULT CURRENT_DATE , TIME TEXT DEFAULT CURRENT_TIME )")
            self.connector.commit()

    def store_visit(self,ip_addr="",url="",browser="",accept_languages=[]):
        
        
        if ip_addr in self.ignore_ips: return
        
        
        with closing(self.connector.cursor()) as cursor:
            
            rows = dict(cursor.execute("SELECT COUNT(*) rows_number FROM METRICS").fetchone())["rows_number"]
            
            
            if rows > self.max_rows:
                self.clear_db()
                
                
            cursor.execute("INSERT INTO METRICS (IP_ADDR,URL,BROWSER,ACCEPT_LANGUAGES) VALUES(?,?,?,?)",(ip_addr,url,str(browser),str(accept_languages)))
            self.connector.commit()
    
    
    def clear_db(self):
        
        with closing(self.connector.cursor()) as cursor:
            
            cursor.execute("DELETE FROM METRICS")
            self.connector.commit()