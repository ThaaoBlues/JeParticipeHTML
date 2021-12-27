from json import *
import database_handler
from random import choices
db = database_handler.DataBase()
from os import path

#db.archive_all()

#db.unfollow("0x1","t")
#db.add_vote(1,1,"choix1",3)
#print(db.get_type("e"))
#print(db.get_followers("u"))
#db.delete_post(1,2)
#print(db.get_results("u",0))
#db.__init_db()
#print(db.get_post(2,1))
#db.register_user(username="test",gender="non_genre",password="prout")
#db.add_post(1,{"header":"post_header","choix":["choix1","choix2"]})
print(db.get_post(1))
#print(db.has_already_voted(1,1))
#print(db.unsanitize("dGVzdA=="))
#db.get_choix_ids(2)
#print(path.dirname(__file__))