import csv
from re import sub
from shutil import move
from json import dumps, loads
from post import Post
from difflib import SequenceMatcher
from os import path

class DataBase:
    
    def __init__(self) -> None:
        self.users_types = ["entreprise","institution publique","utilisateur"]
        if not path.exists("database.csv"):
            self.__init_csv()
    
    def add_post(self,user_id:str,post:dict):
        
        # ajoute le sondage dans la base de donnée
        self.__append_to("user_id",user_id,"post",dumps(post),dict=True)
        self.__append_to("user_id",user_id,"post_stats",dumps({"votes":[0 for _ in range(len(post["choix"]))],"votants":[],"choix":post["choix"]}),dict=True)
 
    def add_vote(self,user_id:str,post_author:str,choix:str,post_id:int):
        
        posts = self.get_posts_stats(post_author)

        posts[post_id]["votants"].append(user_id)
        
        for i in range(len(posts[post_id]["choix"])):
            if posts[post_id]["choix"][i] == choix:
                break
            
        posts[post_id]["votes"][i] = int(posts[post_id]["votes"][i]) +1
                
        self.__write_to("user",post_author,"post_stats",dumps(posts))
                   
    def get_posts_stats(self,post_author:str)->list:
        
        extracted_posts = self.__read_from("user",post_author,"post_stats").replace("'[]'","")
                
        extracted_posts = extracted_posts.replace("'{","{").replace("}'","}").replace("'[","").replace("]'","")

        extracted_posts = extracted_posts[1:-1]

        extracted_posts = extracted_posts.split("}, {")
        
        for i in range(len(extracted_posts)):
            
            if (extracted_posts[i] != None) and (extracted_posts[i] != ""):
               
                if extracted_posts[i][-1] != "}":
                    extracted_posts[i]+= "}"
                   
                if extracted_posts[i][0] != "{":
                    extracted_posts[i] = "{" + extracted_posts[i]

                
        for i in range(len(extracted_posts)):
        
            if (extracted_posts[i] != None) and (extracted_posts[i] != ""):
            
                extracted_posts[i] = loads(extracted_posts[i])
                
            else:
                extracted_posts.pop(i)
                
                
        return extracted_posts
    
    def get_results(self,post_author:str,post_id:int,force_post=False)->list:
        
        if not force_post:
            stats = self.get_posts_stats(post_author)[post_id]
        else:
            stats = force_post
        
            
        n_choix = len(stats["choix"])
        
        ret = {}
        
        for i in range(n_choix):
            
            if len(stats["votants"])>0:
                ret[stats["choix"][i]] = round((stats["votes"][i]/len(stats["votants"])),3)*100
            
            else:
                ret[stats["choix"][i]] = 0
                
            
        return ret
         
    def get_votants(self,post_author:str,post_id:int)->list:
        
        return self.get_posts_stats(post_author)[post_id]["votants"]
 
    def add_follower(self,user_id:str,username:str):
        self.__append_to("user_id",user_id,"followers",username)
        
    def del_follower(self,user_id:str,username:str):
        self.__remove_from("user_id",user_id,"followers",username)
       
    def generate_tl(self,user_id:str)->list:
        
        all_post = []
                
        for follow in self.get_following(user_id):
            follow_id = self.get_user_id(follow)
            
            user_posts = self.get_posts(follow_id)
            
            
            for i in range(len(user_posts)):
            
                stats = self.get_posts_stats(follow)[i]
            
                if user_posts[i] != None:
                    all_post.append(Post(user_posts[i]["header"],user_posts[i]["choix"],user_posts[i]["author"],vote=(user_id in stats["votants"]),resultats = self.get_results(follow,i,force_post=stats),id=i))
                    
            
        return all_post
   
    def match_users(self,query:str)->list:
        users_match = []
        for user in self.get_users():
          if SequenceMatcher(isjunk=None,a=user,b=query).ratio() > 0.60:
              users_match.append({"username":user,"followers":self.get_followers(user),"type":self.get_type(user)})
        return users_match
    
    def get_type(self,username:str)->str:
        return self.__read_from("user",username,"type")
       
    def is_verified(self,username:str):
        return True if self.__read_from("user",username,"verified") == "True" else False
    
    def username_exists(self,username:str)->bool:
        return True if self.__read_from("user",username,"verified") != None else False
       
    def get_user_id(self,username:str)->str:
       return self.__read_from("user",username,"user_id")
    
    def archive_all(self):
        # to archive each 24h
        self.__write_to_all("post","")
        
    def register_user(self,username:str,password="",type="utilisateur",franceconnect=False):
        
        user_id = hex(len(self.get_users())+1)
        self.__add_row([username,user_id,"[]","[]","[]","[]",password,franceconnect,type])
    
    def delete_user(self,user_id:str):
        self.__write_to("user_id",user_id,"","",delete=True)

    def get_following(self,user_id:str)->list:
        L = self.__read_from("user_id",user_id,"following").strip('][').replace("\"","").replace("'","").replace(" ","").split(',')
        L = [p for p in L if p != ""]
        return L
    
    def get_followers(self,username:str)->list:
        return list(filter(None,self.__list_from_str(self.__read_from("user",username,"followers"))))
    
    def follow(self,user_id:str,username:str):
        self.__append_to("user_id",user_id,"following",username)
              
    def unfollow(self,user_id:str,username:str):
        self.__remove_from("user_id",user_id,"following",username)
    
    def get_posts(self,user_id:str,username=False)->list:
        
        if username:
            extracted_posts = self.__read_from("user",user_id,"post").replace("'[]',","")
        else:
            extracted_posts = self.__read_from("user_id",user_id,"post").replace("'[]',","")

        extracted_posts = extracted_posts.replace("'{","{").replace("}'","}").replace("'[","").replace("]'","")

        extracted_posts = extracted_posts[1:-1]

        extracted_posts = extracted_posts.split("}, {")
        
        for i in range(len(extracted_posts)):
            
            if (extracted_posts[i] != None) and (extracted_posts[i] != ""):
               
                if extracted_posts[i][-1] != "}":
                    extracted_posts[i]+= "}"
                   
                if extracted_posts[i][0] != "{":
                    extracted_posts[i] = "{" + extracted_posts[i]

                
        for i in range(len(extracted_posts)):
        
            if (extracted_posts[i] != None) and (extracted_posts[i] != ""):
            
                extracted_posts[i] = loads(extracted_posts[i])
                
            else:
                extracted_posts.pop(i)


        return extracted_posts
                   
    def get_users(self)->list:
        """return a list of all users

        Returns:
            list: [description]
        """
        
        return self.__read_all("user")
    
    def get_password(self,username:str)->list:
        
        return self.__read_from("user",username,"password")
     
    def __init_csv(self,tmp=False):
        with open('database.csv' if not tmp else "database_tmp.csv","w", newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['user', 'user_id', 'post','post_stats','following','followers','password','verified','type'])
            csvfile.close()

    def __add_row(self,row:list):
        """ajoute une ligne

        Args:
            row (list): ligne à ajouter
        """
        with open('database.csv',"a", newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(row)
            csvfile.close()
            
    def __write_to(self,check_key:str,check_value:str,key:str,new_value:str,delete=False):
        """[summary]

        Args:
            check_key (str): clé de valeur de condition
            check_value (str): valeur de condition
            key (str): clé de la valeur à modifier
            new_value (str): valeur à mettre
        """
        
        
        
        with open('database.csv', newline='') as csvfile:
            
            reader = csv.DictReader(csvfile)
            self.__init_csv(tmp=True)

            
            with open('database_tmp.csv',"a", newline='') as tmp_csvfile:
                writer = csv.writer(tmp_csvfile)
                
                for row in reader:
                    if reader.line_num == 1:
                        continue
                    
                    elif row[check_key] == check_value:
                        if not delete:
                            row[key] = new_value
                            writer.writerow(row.values())
                    else:
                        writer.writerow(row.values())
                        
                tmp_csvfile.close()
                csvfile.close()
                
            move('database_tmp.csv','database.csv')
                                        
    def __write_to_all(self,key:str,new_value:list):
        """

        Args:
            key (str): [description]
            new_value (list): [description]
        """
        
        
        with open('database.csv', newline='') as csvfile:
            
            reader = csv.DictReader(csvfile)
            
            with open('database_tmp.csv',"w", newline='') as tmp_csvfile:
                self.__init_csv(tmp=True)
                writer = csv.writer(tmp_csvfile)
                
                
                for row in reader:
                    
                    if reader.line_num == 1:
                        continue
                    
                    row[key] = new_value
                    writer.writerow(row.values())
                        
                tmp_csvfile.close()
                csvfile.close()
                
            move('database_tmp.csv','database.csv')

    def __append_to(self,check_key:str,check_value:str,key:str,new_value:str,dict=False):
        with open('database.csv', newline='') as csvfile:
            
            reader = csv.DictReader(csvfile)
            self.__init_csv(tmp=True)

            
            with open('database_tmp.csv',"a", newline='') as tmp_csvfile:
                writer = csv.writer(tmp_csvfile)
                
                for row in reader:
                    if reader.line_num == 1:
                        continue
                    
                    elif row[check_key] == check_value:
                        
                        if not dict:
                            new_list = self.__list_from_str(row[key])
                            new_list.append(new_value)

                        else:
                            
                            # list of dict processing, special care is needed
                            new_list = row[key].replace("\\'","").replace("'{","{").replace("}'","}").replace("'[","").replace("]'","")

                            if new_list == "[]":
                                new_list = [new_value]
                            
                            else:
                                new_list = new_list[1:-1]
                                new_list = new_list.split("}, {")
                                
                                # re put the brackets removed by the split method
                                for i in range(len(new_list)):
            
                                    if (new_list[i] != None) and (new_list[i] != ""):
                                    
                                        if new_list[i][-1] != "}":
                                            new_list[i]+= "}"
                                        
                                        if new_list[i][0] != "{":
                                            new_list[i] = "{" + new_list[i]
        
                                
                                new_list.append(new_value)
                        
                        
                        row[key] = list(filter(None,new_list))
                        writer.writerow(row.values())
                    else:
                        writer.writerow(row.values())
                        
                tmp_csvfile.close()
                csvfile.close()
                
            move('database_tmp.csv','database.csv')

    def __remove_from(self,check_key:str,check_value:str,key:str,new_value:str):
        with open('database.csv', newline='') as csvfile:
            
            reader = csv.DictReader(csvfile)
            self.__init_csv(tmp=True)

            
            with open('database_tmp.csv',"a", newline='') as tmp_csvfile:
                writer = csv.writer(tmp_csvfile)
                
                for row in reader:
                    if reader.line_num == 1:
                        continue
                    
                    elif row[check_key] == check_value:
                        new_list = self.__list_from_str(row[key])
                        new_list.pop(new_list.index(new_value))
                        row[key] = list(filter(None,new_list))
                        writer.writerow(row.values())
                    else:
                        writer.writerow(row.values())
                        
                tmp_csvfile.close()
                csvfile.close()
                
            move('database_tmp.csv','database.csv')

    def __read_from(self,check_key:str,check_value:str,read_key:str)->str:
        """

        Args:
            check_key (str): clé pour valeur de condition
            check_value (str): valeur de condition
            read_key (str): clé de la valeur à lire

        Returns:
            str: [description]
        """
        
        
        with open('database.csv', newline='') as csvfile:
            
            reader = csv.DictReader(csvfile)
            
            for row in reader:
                if row[check_key] == check_value:
                    return row[read_key]
                
        # nothing has been found return None
        return None
                        
    def __read_all(self,selection:str):
        with open('database.csv', newline='') as csvfile:
            
            reader = csv.DictReader(csvfile)
            
            return [row[selection] for row in reader]
                        
    def sanitize(self,string:str)->str:
        """sanitize and remove all special chars from a string

        Args:
            string (str): [description]

        Returns:
            str: [description]
        """
        
        return sub('\W+','', string)
    
    def __list_from_str(self,string:str)->list:
        return string.strip('][').replace("\"","").replace("'","").replace(" ","").split(',')