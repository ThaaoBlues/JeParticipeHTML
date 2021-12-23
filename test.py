from json import *
import database_handler
from random import choices
db = database_handler.DataBase()

#db.archive_all()

#print(db.get_post("0x1").choix)
#db.add_follower("0x1","test2")
#db.add_follower("0x1","test")
#db.unfollow("0x1","t")
#print(db.get_posts(1))
#db.add_vote(1,1,"choix1",3)
#print(db.get_type("e"))
#print(db.get_followers("u"))
#db.delete_post(1,2)
#print(db.get_results("u",0))
#db.__init_db()
#db.register_user(username="test",gender="non_genre",password="prout")
#db.add_post(1,{"header":"post_header","choix":["choix1","choix2"]})
#print(db.get_post_stats(1,3))
#print(db.has_already_voted(1,1))
#print(db.unsanitize("dGVzdA=="))
db.get_choix_ids(2)