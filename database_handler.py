from random import randint
from re import T, sub
from passlib.handlers.sha2_crypt import sha256_crypt
from post import Post
from difflib import SequenceMatcher
from os import path
from base64 import b64decode, b64encode
import sqlite3 as sql
from os import mkdir,remove
from csv import DictWriter
from zipfile import ZipFile
from contextlib import closing


class DataBase:
    
    def __init__(self) -> None:
        self.users_types = ["entreprise","institution publique","utilisateur"]
        self.gender_types = ["homme","femme","genre_fluide","non_genre","autre","personne_morale"]
        self.publication_types = ["sondage","tirage"]

               
        if not path.exists("static"):
            mkdir("static")
            mkdir("static/users_profile_md")
            mkdir("static/downloads")
        
        
        if not path.exists("database.db"):
            self.__init_db()
            # init database writer
            self.connector = sql.connect("database.db",check_same_thread=False)
            self.connector.row_factory = sql.Row
            
            self.register_user(username="anonyme",email=self.sanitize("vote_exterieur",text=True),gender="autre",password="",type="utilisateur")
            self.set_private_status(1,True)
                    
        # init database writer
        self.connector = sql.connect("database.db",check_same_thread=False)
        self.connector.row_factory = sql.Row
        
    def add_post(self,user_id:int,post:dict):
        with closing(self.connector.cursor()) as cursor:
            # sanitize entries
            post["header"] = self.sanitize(post["header"],text=True)        
            
            cursor.execute("INSERT INTO POSTS (owner_id,header,anon_votes,archived,publication_type) values(?,?,?,?,?)",(user_id,post["header"],post["anon_votes"],False,post["publication_type"]))
            post_id = cursor.lastrowid
            for choix in post["choix"]:
                cursor.execute("INSERT INTO CHOIX (post_id,choix,owner_id,votes) values(?,?,?,?)",(post_id,choix,user_id,0))

            self.connector.commit()
        
    def add_vote(self,user_id:int,owner_id:int,choix:str,post_id:int,user_gender:str,email="anonyme",anon_vote=False):
        
        with closing(self.connector.cursor()) as cursor:
            # to compare with saitized text
            choix = self.sanitize(choix,text=True)

            if anon_vote:

                cursor.execute(f"UPDATE CHOIX SET votes = votes + 1 WHERE owner_id=? AND post_id=? AND choix=?",(owner_id,post_id,choix))


                choix_id = dict(cursor.execute(f"SELECT choix_id FROM CHOIX WHERE owner_id = ? AND post_id = ? AND choix = ?",(owner_id,post_id,choix)).fetchall()[0])["choix_id"]

                username = self.sanitize(email,text=True)
                user_id = 1
                user_gender = "autre"
                cursor.execute(f"INSERT INTO VOTANTS (owner_id,post_id,choix_id,username,voter_id,gender) values(?,?,?,?,?,?)",(owner_id,post_id,choix_id,username,user_id,user_gender))

                self.connector.commit()
            else:

                # make sure the user hasn't already voted
                if self.has_already_voted(user_id,post_id):
                    return

                cursor.execute(f"UPDATE CHOIX SET votes = votes + 1 WHERE owner_id=? AND post_id=? AND choix=?",(owner_id,post_id,choix))


                choix_id = dict(cursor.execute(f"SELECT choix_id FROM CHOIX WHERE owner_id = ? AND post_id = ? AND choix = ?",(owner_id,post_id,choix)).fetchall()[0])["choix_id"]

                username = self.sanitize(self.get_user_name(user_id),text=True)
                cursor.execute(f"INSERT INTO VOTANTS (owner_id,post_id,choix_id,username,voter_id,gender) values(?,?,?,?,?,?)",(owner_id,post_id,choix_id,username,user_id,user_gender))

                self.connector.commit()
                  
    def get_user_name(self,user_id:int)->str:
        """get username from user id

        Args:
            user_id (int): [description]

        Returns:
            str: [description]
        """
        
        
        with closing(self.connector.cursor()) as cursor:
            try:
                return dict(cursor.execute(f"SELECT username FROM USERS WHERE user_id = ?",(user_id,)).fetchall()[0])["username"]
            except:
                # page is being reloaded to many times
                return ""
             
    def get_all_posts_stats(self,owner_id:int)->list:
        
        ret = []
        
        for post in self.get_all_posts(owner_id):
            ret.append(self.get_post_stats(post["post_id"]))
        
        return ret
    
    def get_post_stats(self,post_id:int)->dict:
        
        """retourne un dict de forme:
        {'total_votants': 1, 'choix': {'choix1': 1, 'choix2': 0}, 'genders': {'choix1': {'homme': 0, 'femme': 0, 'genre_fluide': 0, 'non_genre': 0, 'autre': 1}, 'choix2': {'homme': 0, 'femme': 0, 'genre_fluide': 0, 'non_genre': 0, 'autre': 0}}, 'genders_ftolist': {'choix1': [0, 0, 0, 0, 1], 'choix2': [0, 0, 0, 0, 0]}}

        Returns:
            [type]: [description]
        """
        
        
        with closing(self.connector.cursor()) as cursor:
        
            tmp = cursor.execute("SELECT * FROM VOTANTS WHERE post_id=?",(post_id,)).fetchall()
        
        votants = []
        
        # add choix text for each vote
        for row in tmp:
            
            row = dict(row)
            row["username"] = self.unsanitize(row["username"])
            row["choix"] = self.get_choix_text(row["choix_id"])
            
            votants.append(row)
            
        
        ret = {}
        ret["total_votants"] = len(votants)
        
        # init les compteurs de vote pour chaque choix
        ret["choix"] = {}
        
        choix_possibles = self.get_post(post_id)["choix"]
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
        
        with closing(self.connector.cursor()) as cursor:
            return self.unsanitize(dict(cursor.execute("SELECT choix FROM CHOIX WHERE choix_id=?",(choix_id,)).fetchall()[0])["choix"])
        
    def get_post(self,post_id:int):
        with closing(self.connector.cursor()) as cursor:
            post = dict(cursor.execute("SELECT * FROM POSTS WHERE post_id=?",(post_id,)).fetchone())

            post["header"] = self.unsanitize(post["header"])
            choix = [dict(row)["choix"] for row in cursor.execute("SELECT choix FROM CHOIX WHERE post_id=?",(post["post_id"],))]

            post["choix"] = [self.unsanitize(c) for c in choix]
            
            return post
        
    def post_exists(self,post_id:int):
        with closing(self.connector.cursor()) as cursor:
            return cursor.execute("SELECT * FROM POSTS WHERE post_id=?",(post_id,)).fetchall() != []
        
    def get_results(self,post_id:int)->list:

        
        stats = self.get_post_stats(post_id)
        
                
        ret = {}
        
        for c in stats["choix"].keys():

            if stats["total_votants"]>0:
                ret[c] = round((stats["choix"][c]/stats["total_votants"]),3)*100
            
            else:
                ret[c] = 0
        
        return ret
         
    def get_votants(self,post_id:int)->list:
        
        return self.get_post_stats(post_id)["votants"]
       
    def generate_tl(self,user_id:int,self_only=False)->list:
        
        
        # get posts general info as dict
        posts = []
        
        following = self.get_following(user_id) if not self_only else [user_id]
        
        for id in following :
            
            for post in self.get_all_posts(id):
                
                # don't put archived posts if not if "my posts" Tabz
                if (not post["archived"]) or self_only:
                    posts.append(post)
        
        
        # make Post objects and gather all missing data
        for i in range(len(posts)):
            posts[i] = Post(self.unsanitize(posts[i]["header"]),posts[i]["choix"],self.get_user_name(posts[i]["owner_id"]),posts[i]["owner_id"],results=self.get_results(posts[i]["post_id"]),vote=self.has_already_voted(user_id,posts[i]["post_id"]),id=posts[i]["post_id"],stats=self.get_post_stats(posts[i]["post_id"]),archive=posts[i]["archived"],post_type=posts[i]["publication_type"])
        
        
        
        return posts
   
    def match_users(self,query:str)->list:
        
        if query == "":
            return []
        
        
        with closing(self.connector.cursor()) as cursor:
            query = self.sanitize(query)
            users = cursor.execute(f"SELECT username,user_id,type,is_verified FROM USERS WHERE username LIKE '%{query}%' AND username != 'anonyme'").fetchall()
            
            
            #fetchall to dict
            users = [dict(row) for row in users]
            print(users)
            
            for i in range(len(users)):
                users[i]["followers"] = len(cursor.execute("SELECT follower_id FROM FOLLOWERS WHERE user_id=?",(users[i]["user_id"],)).fetchall())
                

                
            #sorting algorithm to classify by best match
            final_users = []
            for i in range(len(users)):
                
                n_diff = abs(len(users[i]["username"])-len(query))
                
                if final_users == []:
                    final_users.append(users[i].copy())
                else:
                    
                    inserted = False
                    # parcours et ajoute à l'index où la différence devient plus grande
                    for j in range(len(final_users)):
                        i_diff = abs(len(final_users[j]["username"])-len(query))
                        if (i_diff>n_diff) or (i_diff==n_diff):
                            final_users.insert(j,users[i].copy())
                            inserted = True
                            break
                            
                    # si aucun username déjà ajouté n'a une différence plus grande, 
                    # ajouter l'utilisateur à la fin de la liste 
                    if not inserted:
                        final_users.append(users[i].copy())
                            
                            
            del users
                              
            return final_users
    
    def get_type(self,user_id:int)->str:
        with closing(self.connector.cursor()) as cursor:
            return cursor.execute("SELECT type FROM USERS WHERE user_id=?",(user_id)).fetchone()[0]
       
    def is_verified(self,user_id:int):
        with closing(self.connector.cursor()) as cursor:
            return cursor.execute("SELECT is_verified FROM USERS WHERE user_id=?",(user_id,)).fetchone()[0]
    
    def username_exists(self,username:str)->bool:
        with closing(self.connector.cursor()) as cursor:
            return cursor.execute("SELECT username FROM USERS WHERE username=?",(username,)).fetchall() != []

    def choix_exists(self,owner_id:int,post_id:int,choix,check_id=False):
        with closing(self.connector.cursor()) as cursor:
            if check_id:
                return cursor.execute("SELECT * FROM CHOIX WHERE choix_id=? AND owner_id=? AND post_id=?",(choix,owner_id,post_id)).fetchall() != []

            else:
                choix = self.sanitize(choix,text=True)
                return cursor.execute("SELECT * FROM CHOIX WHERE choix=? AND owner_id=? AND post_id=?",(choix,owner_id,post_id)).fetchall() != []
            
    def get_user_id(self,username:str,password:str)->str:
        """get user id from username and password by
        checking if passwords match

        Args:
            username (str): [description]
            password (str): [description]

        Returns:
            str: [description]
        """
        with closing(self.connector.cursor()) as cursor:

            users = cursor.execute(f"SELECT user_id,password FROM USERS WHERE username=?",(username,)).fetchall()
            
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
        
        with closing(self.connector.cursor()) as cursor:
            cursor.execute("DELETE FROM POSTS WHERE post_id=? AND owner_id=?",(post_id,user_id))
            cursor.execute("DELETE FROM VOTANTS WHERE post_id=? AND owner_id=?",(post_id,user_id))
            cursor.execute("DELETE FROM CHOIX WHERE post_id=? AND owner_id=?",(post_id,user_id))
            self.connector.commit()
        
    def register_user(self,username="",email="",gender="",password="",type="utilisateur",franceconnect=False,init=False):
        
        with closing(self.connector.cursor()) as cursor:
            pp_url = "https://images.assetsdelivery.com/compings_v2/yupiramos/yupiramos1706/yupiramos170614990.jpg"
            pp_url = self.sanitize(pp_url,text=True)
            
            cursor.execute("INSERT INTO USERS(username,password,age,gender,type,is_verified,is_private,email,pp_url) values(?,?,?,?,?,?,?,?,?)",(username,password,0,gender,type,franceconnect,False,email,pp_url))
            
            self.connector.commit()
            
            
            
            if not init:
                
                user_id = cursor.lastrowid
                
                # init profile md file
                with open(f"static/users_profile_md/{user_id}.md","w") as f:
                    f.write("# Bonjour ! Je suis nouveau ici ;)\n ___ \n## une seconde partie ?\n- eh oui !\n- pour plus d'infos sur le markdown, n'hésitez pas à consulter : [ce site](https://www.markdownguide.org/cheat-sheet/)")
                    f.close()
                
                # follow himself to display his own posts
                self.follow(int(user_id),int(user_id))
                
                return user_id
            
    def delete_user(self,user_id:str):
        with closing(self.connector.cursor()) as cursor:
            cursor.execute("DELETE FROM USERS WHERE user_id=?",(user_id,))
            cursor.execute("DELETE FROM POSTS WHERE owner_id=?",(user_id,))
            cursor.execute("DELETE FROM FOLLOWERS WHERE follower_id=? OR user_id=?",(user_id,user_id))
            cursor.execute("DELETE FROM CHOIX WHERE owner_id=?",(user_id,))
            self.connector.commit()

    def get_following(self,user_id:str)->list:
        """renvoie une list des id utilisateurs suivis

        Args:
            user_id (str): [description]

        Returns:
            list: [description]
        """
        with closing(self.connector.cursor()) as cursor:
            return [dict(row)["user_id"] for row in cursor.execute("SELECT user_id FROM FOLLOWERS WHERE follower_id=?",(user_id,)).fetchall()]
    
    def get_followers(self,user_id:str)->list:
        
        with closing(self.connector.cursor()) as cursor:
            r = cursor.execute("SELECT follower_id FROM FOLLOWERS WHERE user_id=?",(user_id,)).fetchall()
            r = [dict(row)["follower_id"] for row in r]
            return r
    
    def follow(self,user_id:int,target_id:int,is_request=False):
        """user id is the user requesting to follow target_id
        target_id will become user_id in the database and user_id will become follower_id
        so as to get followers_id from an user_id
        Args:
            user_id (int): [description]
            target_id (int): [description]
            is_request (bool, optional): [description]. Defaults to False.
        """
        with closing(self.connector.cursor()) as cursor:
            cursor.execute("INSERT INTO FOLLOWERS (user_id,follower_id,is_request) values(?,?,?)",(target_id,user_id,is_request))
            self.connector.commit()
              
    def unfollow(self,user_id:str,target_id:int):
        with closing(self.connector.cursor()) as cursor:
            cursor.execute(f"DELETE FROM FOLLOWERS where user_id=? AND follower_id=?",(target_id,user_id))
            self.connector.commit()
    
    def get_all_posts(self,user_id:int)->list:
        
        with closing(self.connector.cursor()) as cursor:
            posts = [dict(row) for row in cursor.execute("SELECT * FROM POSTS WHERE owner_id=?",(user_id,)).fetchall()]

            for post in posts:
                choix = [dict(row)["choix"] for row in cursor.execute("SELECT choix FROM CHOIX WHERE post_id=? AND owner_id=?",(post["post_id"],user_id))]
                post["choix"] = [self.unsanitize(c) for c in choix]

            return posts
        
    def get_gender(self,user_id:str):
        with closing(self.connector.cursor()) as cursor:
            return dict(cursor.execute("SELECT gender FROM USERS WHERE user_id = ?",(user_id,)).fetchall()[0])["gender"]

    def has_already_voted(self,user_id:int,post_id:int):
        with closing(self.connector.cursor()) as cursor:
            return True if cursor.execute("SELECT 1 FROM VOTANTS WHERE post_id = ? and voter_id = ?",(post_id,user_id)).fetchall() != [] else False
      
    def anon_votes(self,post_id:int)->bool:
        """renvoie si le vote anonyme est autorisé pour un post ou non
        
        Args:
            post_id (int): [description]

        Returns:
            bool: [description]
        """
        with closing(self.connector.cursor()) as cursor:
            return dict(cursor.execute("SELECT anon_votes FROM POSTS WHERE post_id=?",(post_id,)).fetchall()[0])["anon_votes"]
      
    def get_password(self,user_id:int):
        with closing(self.connector.cursor()) as cursor:
            return dict(cursor.execute("SELECT password FROM USERS WHERE user_id=?",(user_id,)).fetchall()[0])["password"]
    
    def __init_db(self):
                
        c = sql.connect("database.db").cursor()
        c.execute("CREATE TABLE USERS (user_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,username TEXT,password TEXT,age INTEGER,gender TEXT,type TEXT,is_verified BOOL,is_private Bool,email TEXT,pp_url TEXT)")
        c.execute("CREATE TABLE POSTS (post_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,owner_id INTEGER,header TEXT,anon_votes BOOL,archived BOOL,publication_type TEXT)")
        c.execute("CREATE TABLE FOLLOWERS (link_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,user_id INTEGER,follower_id INTEGER,is_request BOOL)")
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
    
    def update_choix(self,post_id:int,choix_id:int,new_text:str):
        """change le texte d'un choix
        (l'assainissement est fait dans la méthode)

        Args:
            post_id (int): [description]
            choix_id (int): [description]
            new_text (str): [description]
        """
        
        new_text = self.sanitize(new_text,text=True)
        with closing(self.connector.cursor()) as cursor:
            cursor.execute("UPDATE CHOIX SET choix=? WHERE post_id=? AND choix_id=?",(new_text,post_id,choix_id))
            self.connector.commit()
        
    def update_anon_votes(self,post_id:int,switch:bool):
        """change le fait qu'on autorise les votes anonymes ou non

        Args:
            post_id (int): [description]
            switch (bool): True si oui False sinon
        """
        
        with closing(self.connector.cursor()) as cursor:
            cursor.execute("UPDATE POSTS SET anon_votes=? WHERE post_id=?",(switch,post_id))
            self.connector.commit()
        
    def update_post_header(self,post_id:int,new_header:bool):
        """
        change le texte de tête du sondage
        (l'assainissement est fait dans la méthode)

        """
        with closing(self.connector.cursor()) as cursor:
            new_header = self.sanitize(new_header,text=True)
            
            cursor.execute("UPDATE POSTS SET header=? WHERE post_id=?",(new_header,post_id))
            self.connector.commit()
         
    def get_choix_ids(self,post_id:int)->list:
        """retourne une liste de toutes les ids des choix d'un post

        Args:
            post_id (int): [description]
            choix (list): [description]

        Returns:
            list: [description]
        """
        with closing(self.connector.cursor()) as cursor:
            choix_ids = [dict(r) for r in cursor.execute("SELECT choix_id FROM CHOIX WHERE post_id=?",(post_id,)).fetchall()]
            choix_ids = [c_id["choix_id"] for c_id in choix_ids]
            
            return choix_ids
    
    def update_post_archive_state(self,post_id:int,archive:bool):
        """set archived to True so the post will not 
        appear in peaple timeline

        Args:
            post_id (int): [description]
        """
        with closing(self.connector.cursor()) as cursor:
            cursor.execute("UPDATE POSTS SET archived=? WHERE post_id = ?",(archive,post_id))
            self.connector.commit()
        
    def user_exists(self,user_id:int)->bool:
        with closing(self.connector.cursor()) as cursor:
            return cursor.execute("SELECT username FROM USERS WHERE user_id=?",(user_id,)).fetchall() != []

    def generate_csv(self,post_id:int)->str:
        """generate a csv file with votes data from the post 

        Args:
            post_id (int): [description]

        Returns:
            str: csv file name
        """
        
        stats = self.get_post_stats(post_id)
        filename = str(randint(0,1234567896))
        filename_zip = filename + ".zip"
        filename_csv = filename + ".csv"
        
        id = 0
        
        # one user per line
        with open(f"static/downloads/users_{filename_csv}","w") as f:
            
            csv_writer = DictWriter(f,["id","genre","choix"])
            csv_writer.writeheader()
            
            # enum choices {'choix' ...}
            for c in stats["choix"].keys():
                # enum genders and their numbers
                for genre,count in list(stats["genders"][c].items()):
                    # write in cv n persones with the gender y that voted on x choice
                    for _ in range(count):
                        row = {"id":id,"genre":genre,"choix":c}
                        csv_writer.writerow(row)
                
                        id += 1
                        
            f.close()
            
        # a line per choice
        with open(f"static/downloads/choix_{filename_csv}","w") as f:
            csv_writer = DictWriter(f,["choix","votes"])
            csv_writer.writeheader()
            
            for choix in stats["choix"].keys():
                row = {"choix":choix,"votes":stats["choix"][choix]}
                csv_writer.writerow(row)
                
            f.close()
            

        # a line per choice genders split
        with open(f"static/downloads/choix_et_genres_{filename_csv}","w") as f:
            fieldnames = ["choix","votes"]
            fieldnames.extend(self.gender_types) 
            csv_writer = DictWriter(f,fieldnames)
            csv_writer.writeheader()
            
            # iter throught each choice
            for choix in stats["choix"].keys():
                row = {"choix":choix,"votes":stats["choix"][choix]}
                
                # get votes count for each gender in one particular choix
                for g in self.gender_types:
                    row[g] = stats["genders"][choix][g]
                    
                csv_writer.writerow(row)
            
            f.close()
            
            
        zipper = ZipFile("static/downloads/"+filename_zip,"w")
        zipper.write(f"static/downloads/users_{filename_csv}")
        zipper.write(f"static/downloads/choix_{filename_csv}")
        zipper.write(f"static/downloads/choix_et_genres_{filename_csv}")
        zipper.close()
        
        
        # delete files except zip
        remove(f"static/downloads/users_{filename_csv}")
        remove(f"static/downloads/choix_{filename_csv}")
        remove(f"static/downloads/choix_et_genres_{filename_csv}")
        
        return filename_zip
    
    def is_private(self,user_id:int)->bool:
        """check if an user is in private mode or not

        Args:
            user_id (int): [description]

        Returns:
            bool: [description]
        """
                
        with closing(self.connector.cursor()) as cursor:
            ret = dict(cursor.execute("SELECT is_private FROM USERS WHERE user_id=?",(user_id,)).fetchone())["is_private"]
                
            return ret
    
    def set_private_status(self,user_id:int,status:bool):
        """set an user pin private mode/remove an user from private mode

        Args:
            status (bool): [description]
        """
        with closing(self.connector.cursor()) as cursor:
            cursor.execute("UPDATE USERS SET is_private=? WHERE user_id=?",(status,user_id))
            self.connector.commit()
        
    def get_user_info(self,user_id:int)->dict:
        """retrieve all data about an user

        Args:
            user_id (int): [description]

        Returns:
            dict: [description]
        """
        with closing(self.connector.cursor()) as cursor:
            return dict(cursor.execute("SELECT username,user_id,type,is_verified FROM USERS WHERE user_id=?",(user_id,)).fetchone())

    def get_follow_requests(self,user_id:int)->list:
        
        """retrieve all follow request to one user
        """
        
        with closing(self.connector.cursor()) as cursor:
    
            return [dict(row) for row in cursor.execute("SELECT follower_id,link_id FROM FOLLOWERS WHERE user_id=? AND is_request=?",(user_id,True)).fetchall()]

    def accept_follow_request(self,link_id:int):
        """update follow line and set is_request to false

        Args:
            link_id (int): [description]
        """
        with closing(self.connector.cursor()) as cursor:
            cursor.execute("UPDATE FOLLOWERS SET is_request=? WHERE link_id=?",(False,link_id))
            self.connector.commit()
         
    def deny_follow_request(self,link_id:int):
        
        """suppress follow line like unfollow but by link_id 

        Args:
            link_id (int): [description]
        """
        
        with closing(self.connector.cursor()) as cursor:
            cursor.execute("DELETE FROM FOLLOWERS WHERE link_id=?",(link_id,))
            self.connector.commit()
        
    def is_link_related_to(self,user_id:int,link_id:int)->bool:
        
        """check if a link_id is related to an user as followed person or not

        Args:
            user_id (int): [description]
            link_id (int): [description]

        Returns:
            bool: [description]
        """
        with closing(self.connector.cursor()) as cursor:
            tmp = cursor.execute("SELECT user_id FROM FOLLOWERS WHERE link_id=? AND user_id=?",(link_id,user_id))
            
            return True if (tmp != [] and tmp != None) else False
    
    def generate_requests_tl(self,user_id:int)->list:
        
        """génère la timeline des profils à accepter/refuser accompagné d'un link_id

        Args:
            user_id (int): [description]

        Returns:
            list: [description]
        """
        
        with closing(self.connector.cursor()) as cursor:
    
            tmp = cursor.execute("SELECT follower_id,link_id FROM FOLLOWERS WHERE user_id=? AND is_request=?",(user_id,True)).fetchall()
            
            tmp = [dict(row) for row in tmp]
            
            # concat user infos and link_id+follower_id (follower_id is useless here)
            for user in tmp:
                user.update(self.get_user_info(user["follower_id"]))
                
            return tmp
    
    def get_posts_count(self,user_id:int):
        with closing(self.connector.cursor()) as cursor:
            return len(cursor.execute("SELECT * FROM POSTS WHERE owner_id=?",(user_id,)).fetchall())

    def get_tirage_participants(self,post_id:int) -> dict:
        """renvoie un dictionnaire avec "ids" : list des ids de votants
        "usernames": list username des votants

        Args:
            post_id (int): [description]

        Returns:
            dict: [description]
        """
        
        with closing(self.connector.cursor()) as cursor:
            tmp = [dict(r) for r in cursor.execute("SELECT voter_id, username FROM VOTANTS WHERE post_id=?",(post_id,)).fetchall()]
            
            ret = {}
            ret["ids"] = []
            ret["usernames"] = []
            ret["genders"] = []
            ret["emails"] = []
            
            for ele in tmp:
                i = randint(0,len(ret["ids"]))
                ret["ids"].insert(i,ele["voter_id"])
                ret["usernames"].insert(i,self.unsanitize(ele["username"]))
                ret["genders"].insert(i,self.get_gender(int(ele["voter_id"])))
                ret["emails"].insert(i,self.get_email(int(ele["voter_id"])))


            return ret
    
    def get_email(self,user_id:int)->str:
        """return the unsanitized email addr of an user

        Args:
            user_id (int): [description]
        """
        
        with closing(self.connector.cursor()) as cursor:
            tmp = dict(cursor.execute("SELECT email FROM USERS WHERE user_id=?",(user_id,)).fetchone())["email"]
            return self.unsanitize(tmp)
            
    def update_email(self,user_id:int,email:str):
        
        with closing(self.connector.cursor()) as cursor:
            
            email = self.sanitize(email,text=True)
            cursor.execute("UPDATE USERS SET email=? WHERE user_id=?",(email,user_id))
            self.connector.commit()
            
    def email_exists(self,email:str)->bool:
        """[summary]

        Args:
            mail (str): [description]

        Returns:
            bool: [description]
        """
        email = self.sanitize(email,text=True)
        
        with closing(self.connector.cursor()) as cursor:
            
            tmp = cursor.execute("SELECT * FROM USERS WHERE email=?",(email,)).fetchall()
            
            return tmp != []
        
    def get_pp_url(self,user_id:int)->str:
        
        with closing(self.connector.cursor()) as cursor:
            return self.unsanitize(dict(cursor.execute("SELECT pp_url FROM USERS WHERE user_id=?",(user_id,)).fetchone())["pp_url"])
    
    def set_pp_url(self,user_id:int,pp_url:str):
        
        with closing(self.connector.cursor()) as cursor:
            pp_url = self.sanitize(pp_url,text=True)
            cursor.execute("UPDATE USERS SET pp_url=? WHERE user_id=?",(pp_url,user_id))
            self.connector.commit()
            
            
    def get_full_database(self):
        """return all the database content
        as a gigantic dict, one key for each table
        each row is a list of dict {"key":value}
        """
        database = {}
        
        with closing(self.connector.cursor()) as cursor:
            for row in cursor.execute("SELECT name FROM sqlite_schema WHERE type ='table' AND name NOT LIKE 'sqlite_%'").fetchall():
                database[dict(row)["name"]] = ""
                
            
            for table in database.keys():
                t_content = cursor.execute(f"SELECT * FROM {table}")
                database[table] = [dict(row) for row in t_content]
                
            return database