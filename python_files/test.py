from json import *
import database
from random import choices
db = database.DataBase()

#db.archive_all()

#db.add_user("test2","12345")
#db.add_post("0x1",{"header":"ceci est un post","choix":["choix 1","choix 2"],"author":"lex"})
#print(db.get_post("0x1").choix)
#db.add_follower("0x1","test2")
#db.add_follower("0x1","test")
#db.unfollow("0x1","t")
#print(db.get_posts("0x1")[2])
#db.add_vote("0x2","lex","choix1",0)
print(db.get_results("lex",0))