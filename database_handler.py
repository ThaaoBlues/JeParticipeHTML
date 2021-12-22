from re import sub, escape
from shutil import move
from json import dumps, loads
from sqlite3.dbapi2 import Cursor

from passlib.handlers.sha2_crypt import sha256_crypt, sha512_crypt
from post import Post
from difflib import SequenceMatcher
from os import path
from base64 import b64decode, b64encode
import sqlite3 as sql

class DataBase:
    
    def __init__(self) -> None:
        self.users_types = ["entreprise","institution publique","utilisateur"]
        self.gender_types = ["homme","femme","genre_fluide","non_genre","autre"]
        
        if not path.exists("database.db"):
            self.__init_db()
            # init database writer
            self.connector = sql.connect("database.db",check_same_thread=False)
            self.connector.row_factory = sql.Row

            self.cursor = self.connector.cursor()
        
            
            self.register_user(username="compteur_utilisateurs",gender="autre",type="compteur",franceconnect=True,init=True)
        
        
        # init database writer
        self.connector = sql.connect("database.db",check_same_thread=False)
        self.connector.row_factory = sql.Row
        self.cursor = self.connector.cursor()
        
        
            
    def add_post(self,user_id:int,post:dict):
        
        # sanitize entries
        post["header"] = self.sanitize(post["header"],text=True)        
        
        self.cursor.execute("INSERT INTO POSTS (owner_id,header,anon_votes) values(?,?,?)",(user_id,post["header"],post["anon_votes"]))
        post_id = self.cursor.lastrowid
        for choix in post["choix"]:
            self.cursor.execute("INSERT INTO CHOIX (post_id,choix,owner_id,votes) values(?,?,?,?)",(post_id,choix,user_id,0))

        self.connector.commit()
        
    def add_vote(self,user_id:int,owner_id:int,choix:str,post_id:int,user_gender:str,anon_vote=False):
        
        # to compare with saitized text
        choix = self.sanitize(choix,text=True)
        
        if anon_vote:
                
            self.cursor.execute(f"UPDATE CHOIX SET votes = votes + 1 WHERE owner_id=? AND post_id=? AND choix=?",(owner_id,post_id,choix))
            
            
            choix_id = dict(self.cursor.execute(f"SELECT choix_id FROM CHOIX WHERE owner_id = ? AND post_id = ? AND choix = ?",(owner_id,post_id,choix)).fetchall()[0])["choix_id"]
            
            username = "anonymous"
            self.cursor.execute(f"INSERT INTO VOTANTS (owner_id,post_id,choix_id,username,voter_id,gender) values(?,?,?,?,?,?)",(owner_id,post_id,choix_id,username,user_id,user_gender))
            
            self.connector.commit()
        else:
            
            # make sure the user hasn't already voted
            if self.has_already_voted(user_id,post_id):
                return
            
            self.cursor.execute(f"UPDATE CHOIX SET votes = votes + 1 WHERE owner_id=? AND post_id=? AND choix=?",(owner_id,post_id,choix))
            
            
            choix_id = dict(self.cursor.execute(f"SELECT choix_id FROM CHOIX WHERE owner_id = ? AND post_id = ? AND choix = ?",(owner_id,post_id,choix)).fetchall()[0])["choix_id"]
            
            username = self.get_user_name(user_id)
            self.cursor.execute(f"INSERT INTO VOTANTS (owner_id,post_id,choix_id,username,voter_id,gender) values(?,?,?,?,?,?)",(owner_id,post_id,choix_id,username,user_id,user_gender))
            
            self.connector.commit()
                  
    def get_user_name(self,user_id:int)->str:
        """get username from user id

        Args:
            user_id (int): [description]

        Returns:
            str: [description]
        """
        return dict(self.cursor.execute(f"SELECT username FROM USERS WHERE user_id = ?",(user_id,)).fetchall()[0])["username"]
              
    def get_all_posts_stats(self,owner_id:int)->list:
        
        ret = []
        
        for post in self.get_all_posts(owner_id):
            ret.append(self.get_post_stats(owner_id,post["post_id"]))
        
        return ret
    
    def get_post_stats(self,owner_id:int,post_id:int)->dict:
        
        """retourne un dict de forme:
        {'total_votants': 1, 'choix': {'choix1': 1, 'choix2': 0}, 'genders': {'choix1': {'homme': 0, 'femme': 0, 'genre_fluide': 0, 'non_genre': 0, 'autre': 1}, 'choix2': {'homme': 0, 'femme': 0, 'genre_fluide': 0, 'non_genre': 0, 'autre': 0}}, 'genders_ftolist': {'choix1': [0, 0, 0, 0, 1], 'choix2': [0, 0, 0, 0, 0]}}

        Returns:
            [type]: [description]
        """
        
        tmp = self.cursor.execute("SELECT * FROM VOTANTS WHERE owner_id=? AND post_id=?",(owner_id,post_id)).fetchall()
        
        votants = []
        
        # add choix text for each vote
        for row in tmp:
            
            row = dict(row)
            row["choix"] = self.get_choix_text(row["choix_id"])
            
            votants.append(row)
        
        ret = {}
        ret["total_votants"] = len(votants)
        
        # init les compteurs de vote pour chaque choix
        ret["choix"] = {}
        
        choix_possibles = self.get_post(owner_id,post_id)["choix"]
        for c in choix_possibles:
            ret["choix"][c] = 0
            
        for v in votants:
            # incrémente les compteurs
            ret["choix"][v["choix"]]+=1
            
            
        # initialise le dictionnaire des choix
        # corrélés au compteur de genre
        ret["genders"] = {}
        ret["genders_ftolist"] = {}
        
        for c in choix_possibles:
            ret["genders"][c] = dict((g,0) for g in self.gender_types)
            
            # compteur de genres sous forme de liste,
            # plus facile à énumérer dans un template jinja
            ret["genders_ftolist"][c] = [0 for _ in range(len(self.gender_types))]

        
        # recense les genres
        for v in votants:
            # incrémente les compteurs
            ret["genders"][v["choix"]][v["gender"]] += 1
            ret["genders_ftolist"][v["choix"]][self.gender_types.index(v["gender"])] += 1
            
        
        
        return ret     
        
    def get_choix_text(self,choix_id:int):
        """return the text corresponding to a choix_id

        Args:
            choix_id (int): [description]

        Returns:
            [type]: [description]
        """
        
        
        return self.unsanitize(dict(self.cursor.execute("SELECT choix FROM CHOIX WHERE choix_id=?",(choix_id,)).fetchall()[0])["choix"])
        
    def get_post(self,owner_id:int,post_id:int):
        
        post = dict(self.cursor.execute("SELECT * FROM POSTS WHERE owner_id=? AND post_id=?",(owner_id,post_id)).fetchone())

        post["header"] = self.unsanitize(post["header"])
        choix = [dict(row)["choix"] for row in self.cursor.execute("SELECT choix FROM CHOIX WHERE post_id=? AND owner_id=?",(post["post_id"],owner_id))]
        
        post["choix"] = [self.unsanitize(c) for c in choix]
        
        return post
        
    def post_exists(self,post_id:int):
        return self.cursor.execute("SELECT * FROM POSTS WHERE post_id = ?",(post_id,)).fetchall() != []
        
    def get_results(self,owner_id:int,post_id:int)->list:

        
        stats = self.get_post_stats(owner_id,post_id)
        
                
        ret = {}
        
        for c in stats["choix"].keys():

            if stats["total_votants"]>0:
                ret[c] = round((stats["choix"][c]/stats["total_votants"]),3)*100
            
            else:
                ret[c] = 0
        
        return ret
         
    def get_votants(self,post_author:str,post_id:int)->list:
        
        return self.get_posts_stats(post_author)[post_id]["votants"]
                 
    def del_follower(self,user_id:str,username:str):
        self.__remove_from("user_id",user_id,"followers",username)
       
    def generate_tl(self,user_id:int)->list:
        
        
        # get posts general info as dict
        posts = []
        
        for id in self.get_following(user_id):
            
            for post in self.get_all_posts(id):
                posts.append(post)
        
        
        # make Post objects and gather all missing data
        for i in range(len(posts)):
            posts[i] = Post(self.unsanitize(posts[i]["header"]),posts[i]["choix"],self.get_user_name(posts[i]["owner_id"]),posts[i]["owner_id"],results=self.get_results(posts[i]["owner_id"],posts[i]["post_id"]),vote=self.has_already_voted(user_id,posts[i]["post_id"]),id=posts[i]["post_id"],stats=self.get_post_stats(posts[i]["owner_id"],posts[i]["post_id"]))
            
        return posts
   
    def match_users(self,query:str)->list:
        query = self.sanitize(query)
        # dict {"username":user,"followers":self.get_followers(user),"type":self.get_type(user)}
        users = self.cursor.execute("SELECT username,user_id,type,is_verified FROM USERS WHERE username=?",(query,)).fetchall()
        
        #fetchall to dict
        users = [dict(row) for row in users]
        
        for user in users:
            user["followers"] = len(self.get_followers(user["user_id"]))
        
        return users     
    
    def get_type(self,user_id:int)->str:
        return self.cursor.execute("SELECT type FROM USERS WHERE user_id=?",(user_id)).fetchone()[0]
       
    def is_verified(self,user_id:int):
        return self.cursor.execute("SELECT is_verified FROM USERS WHERE user_id=?",(user_id,)).fetchone()[0]
    
    def username_exists(self,username:str)->bool:
        return self.match_users(username) != []
    
    def choix_exists(self,owner_id:int,post_id:int,choix:str):
        choix = self.sanitize(choix,text=True)
        return self.cursor.execute("SELECT * FROM CHOIX WHERE choix=? AND owner_id=? AND post_id=?",(choix,owner_id,post_id)).fetchall() != []
    
    def get_user_id(self,username:str,password:str)->str:
        """get user id from username and password by
        checking if passwords match

        Args:
            username (str): [description]
            password (str): [description]

        Returns:
            str: [description]
        """
        
        users = self.cursor.execute(f"SELECT user_id,password FROM USERS WHERE username=?",(username,)).fetchall()
        
        users = [dict(row) for row in users]
        
        for user in users:
            if user["user_id"] != 1:
                if sha256_crypt.verify(password,user["password"]):
                    return user["user_id"]
        
        return None
                  
    def delete_post(self,user_id:str,post_id:str):
        """delete all data about a post
        
        Args:
            user_id (str): post's owner id
            post_id (str): post id
        """
        
        
        self.cursor.execute("DELETE FROM POSTS WHERE post_id=? AND owner_id=?",(post_id,user_id))
        self.cursor.execute("DELETE FROM VOTANTS WHERE post_id=? AND owner_id=?",(post_id,user_id))
        self.cursor.execute("DELETE FROM CHOIX WHERE post_id=? AND owner_id=?",(post_id,user_id))
        self.connector.commit()
    
    def archive_all(self):
        # to archive each 24h
        self.__write_to_all("post","")
        
    def register_user(self,username="",gender="",password="",type="utilisateur",clear_password="",franceconnect=False,init=False):
        
        self.cursor.execute("INSERT INTO USERS(username,password,age,gender,type,is_verified) values(?,?,?,?,?,?)",(username,password,0,gender,type,franceconnect))
        
        self.connector.commit()
        
        
        
        if not init:
            
            user_id = self.get_user_id(username,clear_password)

            # add user to followers counter
            self.follow(int(user_id),1)
            
            # follow himself to display his own posts
            self.follow(int(user_id),int(user_id))
            
    def delete_user(self,user_id:str):
        self.cursor.execute("DELETE FROM USERS WHERE user_id=?",(user_id))
        self.cursor.execute("DELETE FROM POSTS WHERE owner_id=?",(user_id))
        self.cursor.execute("DELETE FROM FOLLOWERS WHERE follower_id=? OR user_id=?",(user_id,user_id))
        self.connector.commit()

    def get_following(self,user_id:str)->list:
        return [dict(row)["user_id"] for row in self.cursor.execute("SELECT user_id FROM FOLLOWERS WHERE follower_id=?",(user_id,)).fetchall()]
    
    def get_followers(self,user_id:str)->list:
        r = self.cursor.execute("SELECT follower_id FROM FOLLOWERS WHERE user_id=?",(user_id,)).fetchall()
        r = [dict(row) for row in r]
        return r
    
    def follow(self,user_id:int,target_id:int):
        
        self.cursor.execute("INSERT INTO FOLLOWERS (user_id,follower_id) values(?,?)",(target_id,user_id))
        self.connector.commit()
              
    def unfollow(self,user_id:str,target_id:int):
        self.cursor.execute(f"DELETE FROM FOLLOWERS where user_id=? AND follower_id=?",(target_id,user_id))
        self.connector.commit()
    
    def get_all_posts(self,user_id:int)->list:
        
        posts = [dict(row) for row in self.cursor.execute("SELECT * FROM POSTS WHERE owner_id=?",(user_id,)).fetchall()]

        for post in posts:
            choix = [dict(row)["choix"] for row in self.cursor.execute("SELECT choix FROM CHOIX WHERE post_id=? AND owner_id=?",(post["post_id"],user_id))]
            post["choix"] = [self.unsanitize(c) for c in choix]

        return posts
        
    def get_gender(self,user_id:str):

        return dict(self.cursor.execute("SELECT gender FROM USERS WHERE user_id = ?",(user_id,)).fetchall()[0])["gender"]

    def has_already_voted(self,user_id:int,post_id:int):
        
        return True if self.cursor.execute("SELECT 1 FROM VOTANTS WHERE post_id = ? and voter_id = ?",(post_id,user_id)).fetchall() != [] else False
      
    def anon_votes(self,post_id:int)->bool:
        """renvoie si le vote anonyme est autorisé pour un post ou non
        
        Args:
            post_id (int): [description]

        Returns:
            bool: [description]
        """
        return dict(self.cursor.execute("SELECT anon_votes FROM POSTS WHERE post_id=?",(post_id,)).fetchall()[0])["anon_votes"]
      
    def get_password(self,user_id:int):
        
        return dict(self.cursor.execute("SELECT password FROM USERS WHERE user_id=?",(user_id,)).fetchall()[0])["password"]
    
    def __init_db(self,tmp=False):
                
        c = sql.connect("database.db").cursor()
        c.execute("CREATE TABLE USERS (user_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,username TEXT,password TEXT,age INTEGER,gender TEXT,type TEXT,is_verified BOOL)")
        c.execute("CREATE TABLE POSTS (post_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,owner_id INTEGER,header TEXT,anon_votes BOOL)")
        c.execute("CREATE TABLE FOLLOWERS (link_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,user_id INTEGER,follower_id INTEGER)")
        c.execute("CREATE TABLE CHOIX (choix_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,owner_id INTEGER,post_id INTEGER,choix TEXT,votes INTEGER)")
        c.execute("CREATE TABLE VOTANTS (vote_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,owner_id INTEGER,post_id INTEGER,choix_id INTEGER,username TEXT,voter_id INTEGER,gender TEXT)")
        
        c.close()
                        
    def sanitize(self,string:str,text=False)->str:
        """sanitize and remove all special chars from a string

        Args:
            string (str): [description]

        Returns:
            str: [description]
        """
        if text:
            string = b64encode(bytes(string,"utf-8")).decode("utf-8")
        else:
            string = sub("\W+",'',string)
            
        return string
    
    def unsanitize(self,string:bytes)->str:
        
        return b64decode(string).decode("utf-8")