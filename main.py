
from post import Post
from passlib.handlers.sha2_crypt import sha256_crypt
from flask import Flask, session, url_for, render_template,request,redirect
import database_handler
from flask_login import login_required, login_user, logout_user, LoginManager, UserMixin, current_user
from random import choices, randint
from os import path
from markdown import markdown
from html_sanitizer import Sanitizer
from time import sleep

#init flask app
app = Flask(__name__)
#app.config["UPLOAD_FOLDER"] = "static/users_profile.md"

db = database_handler.DataBase()



# sessions and login manager stuff

login_manager = LoginManager()

login_manager.init_app(app)

app.secret_key = "".join(choices("1234567890°+AZERTYUIOP¨£µQSDFGHJKLM%WXCVBN?./§<>azertyuiopqsdfghjklmwxcvbn",k=1024))


class User(UserMixin):
    
    
    def __init__(self, name="", id=0, active=True,gender="autre"):
        self.name = name
        self.id = int(id)
        self.active = active
        self.gender = gender

    def is_active(self):
        # Here you should write whatever the code is
        # that checks the database if your user is active
        return self.active

    def is_anonymous(self):
        return False

    def is_authenticated(self):
        return True

@login_manager.user_loader
def user_loader(user_id):
    
    # prevent multiples refresh from one ip to make server crash
    while True:
        try:
            user = User(name=db.get_user_name(user_id),id=user_id,gender=db.get_gender(user_id))
            return user
        except:
            print("exception")
            sleep(2)


        
        
@login_manager.unauthorized_handler
def unauthorized_handler():
    return redirect(url_for("login"))

@app.route("/")
def acceuil():
    
    return redirect(url_for("login"))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template("login.html")
    
    
    elif(request.form.get('username',default=None) != None ) and (request.form.get('password',default=None) != None):
    
        if request.form.get('username',default=None) != None:
            
            
            username = db.sanitize(request.form.get('username'))

            if (not db.username_exists(username)) or (username == "compteur_utilisateurs"):
                return redirect(url_for("login"))
            
            user_id = db.get_user_id(username,request.form.get('password'))
            
            if user_id == None:
                return redirect(url_for("login"))
            
            is_auth = sha256_crypt.verify(request.form.get('password'),db.get_password(user_id))

            if is_auth:
                user = User(name=username,id=user_id,gender=db.get_gender(user_id)) 
                login_user(user,remember=True)
            
            return redirect(url_for('home'))

    else:
        return redirect(url_for("login"))

 
@app.route('/partage',methods=["GET","POST"])
def shared():
    
    """penser à metre l'arg vote dans le script dans chaque template et mettre la condition de vote dans le template share"""
    
    if request.method == "GET":

        if (request.args.get("owner_id",default=None) != None) and (request.args.get("post_id",default=None) != None) and (request.args.get("results",default=None)!=None):
            
            
            # check if all args are of the correct type
            try:
                post_id = request.args.get("post_id",type=int)                
                owner_id = request.args.get("owner_id",type=int)
                vote = True if request.args.get("results") == "True" else False
            except ValueError:
                return render_template("page_message.html",message="Un paramètre de votre requète a été mal-formé :/",texte_btn="Revenir à l'acceuil",lien="/home")
            
                        
            if (db.post_exists(post_id)):
                post = db.get_post(owner_id,post_id)

                post = Post(post["header"],post["choix"],db.get_user_name(post["owner_id"]),post["owner_id"],id=post["post_id"],results=db.get_results(post["owner_id"],post["post_id"]),anon_votes=post["anon_votes"],vote=vote)

                return render_template("share_post.html",post = post)
                
            else:
                return render_template("page_message.html",message="Cet utilisateur n'existe pas :/",texte_btn="Revenir à l'acceuil",lien="/home")

        else:
            return render_template("page_message.html",message="Le sondage que vous demandez n'est malheureusement pas/plus disponible ou n'a jamais existé ou un paramètre de votre requète a été mal-formé :/ :/",texte_btn="Revenir à l'acceuil",lien="/home")
    
    
    elif request.method == "POST":
        
        # anonymous vote
        choix = request.form.get("choix",default=None)
        author_id = request.form.get("author_id",default=None)
        post_id = request.form.get("post_id",default=None)
        if (choix != None) and  (author_id != None) and  (post_id != None):

            choix = request.form.get("choix")
            # check if post_id is an int
            try:
                post_id = request.form.get("post_id",type=int)
                author_id = request.form.get("author_id",type=int)
                
            except ValueError:
                return render_template("page_message.html",message="Un paramètre de votre requète a été mal-formé :/",texte_btn="Revenir à l'acceuil",lien="/login")
            
            
            # makes sure post exists, selected choice exists and anon_votes is set to True
            if (db.choix_exists(author_id,post_id,choix)) and (db.anon_votes(post_id)):
                
                db.add_vote(0,author_id,choix,post_id,"autre",anon_vote=True)
        
                return redirect(f"/partage?owner_id={author_id}&post_id={post_id}&results=True")
            else:
                return render_template("page_message.html",message="Le sondage que vous demandez n'est malheureusement pas/plus disponible ou n'a jamais existé :/",texte_btn="Revenir à l'acceuil",lien="/login")
        else:
            return render_template("page_message.html",message="Le sondage que vous demandez n'est malheureusement pas/plus disponible ou n'a jamais existé :/",texte_btn="Revenir à l'acceuil",lien="/login")

                
@app.route('/home',methods=['GET'])
@login_required
def home():
    
    # prevent user from spam requests
    while True:
        try:
            sondages = db.generate_tl(current_user.id)
            break
        except:
            logout_user()
            return redirect("/")
            
    return render_template("home.html",username = current_user.name,sondages = sondages)

@app.route("/add_vote",methods=["POST"])
@login_required
def add_vote():
    
    if (request.form.get("choix",default=None) != None) and  (request.form.get("author_id",default=None) != None) and  (request.form.get("post_id",default=None) != None):


        choix = request.form.get("choix")
        
         # check if post_id is an int
        try:
            post_id = request.form.get("post_id",type=int)
        except ValueError:
            return render_template("page_message.html",message="Un paramètre de votre requète a été mal-formé :/",texte_btn="Revenir à l'acceuil",lien="/login")
        # check if author_id is an int
        try:
            author_id = request.form.get("author_id",type=int)
        except ValueError:
            return render_template("page_message.html",message="Un paramètre de votre requète a été mal-formé :/",texte_btn="Revenir à l'acceuil",lien="/login")
            

        if (db.choix_exists(author_id,post_id,choix)):
            
            db.add_vote(current_user.id,author_id,choix,post_id,current_user.gender)
            
    return redirect(url_for("home"))

@app.route("/recherche",methods=["GET","POST"])
@login_required
def recherche():



    
    if request.method == "POST":
        if (request.form.get("user_id",default=None) != None) and (request.form.get("action",default=None) != None):
           
            from_profile = True if request.form.get("from_profile",default=None) else False

           
            # don't forget to check if the parameter is of the right type
            try:
                user_id = request.form.get("user_id",type=int)
            except ValueError:
                return render_template("page_message.html",message="Un paramètre de votre requète a été mal-formé :/",texte_btn="Revenir à l'acceuil",lien="/home")

                
                
            if request.form.get("action") == "unfollow":
                
                db.unfollow(current_user.id,user_id)
                
            elif request.form.get("action") == "follow":
                
                db.follow(current_user.id,user_id)
            
            if from_profile:
                return redirect(f"/profil?user_id={user_id}")
            else:
                return redirect(request.url)
        
        else:
            return render_template("page_messae.html")
    
    
    
    elif request.args.get("req",default=None) != None:
        req = db.sanitize(request.args.get("req"))

        profils = []
        following = db.get_following(current_user.id)
        
        profils = db.match_users(req)
        
        error = profils == []

        return render_template("search.html",following = following,profils=profils,error=error)
    else:
        return render_template("search.html",profils=[],req="")


@app.route("/creer_sondage",methods=["GET","POST"])
@login_required
def sondage_form():
    
    
    if request.method == "GET":
        return render_template("create_post.html",username=current_user.name)
    
    
    elif request.method == "POST":
        
        post_header = request.form.get("post_header",default=None)
        choix = request.form.get("choix",default=None)
        
        try:
            anon_votes = request.form.get("anon_votes",default=False,type=bool)
        except ValueError:
            return render_template("page_message.html",message="Un paramètre de votre requète a été mal-formé :/",texte_btn="Revenir à l'acceuil",lien="/home")

        
        
        if (choix != None) and (post_header != None) and (anon_votes != None):
            
            #remove any empty string
            choix = list(filter(None, choix.split("/")))
            # tries to not transmit XSS
            choix = [db.sanitize(c,text=True) for c in choix]
            
            
            if len(choix) == 1:
                return render_template("page_message.html",message="Veuillez remplir le champ des choix comme ceci : choix1/choix2/choix3....",texte_btn="Refaire le sondage",btn_url="/creer_sondage")
                        
            db.add_post(current_user.id,{"header":post_header,"choix":choix,"anon_votes":anon_votes})
            
            return render_template("page_message.html",message="Sondage publié ! Prenez un café et attendez les retours ;)",texte_btn="Revenir à l'acceuil",lien="/home")

            
        else:
            return render_template("page_message.html",message="Veuillez remplir la totalité des champs.",texte_btn="Refaire le sondage",btn_url="/creer_sondage")


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect("/")


@app.route('/register',methods=["POST"])
def register():
    
    
    
    if (request.form.get("username",None) != None) and (request.form.get("password",None) != None) and (request.form.get("type",default=None).lower() in db.users_types) and (request.form.get("genre",default=None).lower().replace(" ","_") in db.gender_types):
        
        username = db.sanitize(request.form.get("username"))
        
        gender = request.form.get("genre",type=str).lower().replace(" ","_")
        
        # if user already exists, abort and return a nice message
        if db.username_exists(username):
            return render_template("page_message.html",message="Ce nom d'utilisateur existe déjà :/ Ne vous inquiétez pas, vous avez assez d'imagination pour en trouver un autre ;)",texte_btn="Revenir à la page d'enregistrement",lien="/login")
        
        db.register_user(username=username,gender=gender ,password=sha256_crypt.hash(request.form.get("password")),type=request.form.get("type").lower(),franceconnect=True,clear_password=request.form.get("password"))
      
        return render_template("page_message.html",message="Vous avez bien été enregistré ! Clickez sur le bouton pour revenir à la page de connexion ;)",texte_btn="Revenir à l'acceuil",lien="/login")
    
    else:
        return render_template("page_message.html",message="Un problème est survenu lors de votre enregistrement :/",texte_btn="Revenir à l'acceuil",lien="/")
    

@app.route("/stats",methods=["GET"])
@login_required
def stats():
    
    # page de stats et possibilité de delete le sondage
    
    if request.method == "GET":
    
        if (request.args.get("username",default=None) != None) and (request.args.get("post_id",default=None) != None):
            
            username = db.sanitize(request.args.get("username",type=str))
            
            # check if post_id is an int
            try:
                post_id = request.args.get("post_id",type=int)
            except ValueError:
                return render_template("page_message.html",message="Un paramètre de votre requète a été mal-formé :/",texte_btn="Revenir à l'acceuil",lien="/home")
            
            post_dict = db.get_post(current_user.id,post_id)
            
            stats = db.get_post_stats(current_user.id,post_id)
            
            post = Post(post_dict["header"],post_dict["choix"],db.get_user_name(post_dict["owner_id"]),post_dict["owner_id"],results=db.get_results(current_user.id,post_id),vote=db.has_already_voted(current_user.id,post_id),id=post_id,stats=stats)
                    
            
            # vérifie que le post existe bien et appartient bien à l'utilisateur connecté
            if (current_user.name == username) and  (db.post_exists(post_id)):
                
                resultats = db.get_results(current_user.id,post_id)
                
                # to make the charts
                colors = [ f"rgb({randint(0, 255)},{randint(0, 255)},{randint(0, 255)})" for _ in range(len(resultats))]

                genders = {"list":[g for g in db.gender_types],"colors":[ f"rgb({randint(0, 255)},{randint(0, 255)},{randint(0, 255)})" for _ in range(len(db.gender_types)+1)]}
                          
                # choix without special chars to put as variable names
                sanitized_choix = {}
                for c in post_dict["choix"]:
                    sanitized_choix[c] = db.sanitize(c)
                
                return render_template("stats.html",username=current_user.name,post = post,resultats=resultats,resultats_values=list(resultats.values()),chart_colors=colors,genders=genders,sanitized_choix=sanitized_choix)
                
            else:
                return render_template("page_message.html",message="Vous demandez les statistiques d'un sondage qui n'est pas le votre :/",texte_btn="Revenir à l'acceuil",lien="/home")

        else:
            return render_template("page_message.html",message="Le sondage que vous demandez n'est malheureusement pas/plus disponible :/",texte_btn="Revenir à l'acceuil",lien="/home")
    
@app.route("/mes_sondages",methods=["GET","POST"])
@login_required
def mes_sondages():
    sondages = db.generate_tl(current_user.id,self_only=True)
        
    return render_template("my_posts.html",username = current_user.name,sondages = sondages)

@app.route("/parametres_sondage",methods=["GET","POST"])
@login_required
def parametres_sondage():
    
    
    if request.method == "GET":
        
        # check request args
        try:
            post_id = request.args.get("post_id",type=int,default=None)
            owner_id = request.args.get("owner_id",type=int,default=None)
        except ValueError:
            return render_template("page_message.html",message="Un paramètre de votre requète a été mal-formé :/",texte_btn="Revenir à l'acceuil",lien="/mes_sondages")

        if (post_id == None) or (owner_id == None):
            return render_template("page_message.html",message="Un paramètre de votre requète a été mal-formé :/",texte_btn="Revenir à l'acceuil",lien="/mes_sondages")
        
        #check if post exists and belongs to the current user
        if db.post_exists(post_id) and (owner_id == current_user.id):
            post = db.get_post(owner_id,post_id)
            post = Post(post["header"],post["choix"],db.get_user_name(post["owner_id"]),post["owner_id"],id=post["post_id"],anon_votes=post["anon_votes"],choix_ids=db.get_choix_ids(post["post_id"]))
            
            return render_template("post_settings.html",post=post,username=current_user.name)
        
        # else throw an error message
        else:
            
            return render_template("page_message.html",message="Le sondage que vous demandez n'est malheureusement pas/plus disponible pour vous ou n'a jamais existé",texte_btn="Revenir à l'acceuil",lien="/mes_sondages")


            
    
    elif request.method == "POST":
        
        post_header = request.form.get("post_header",default=None)
        choix = request.form.get("choix",default=None)
        # check if everything is from the right type
        try:
            anon_votes = request.form.get("anon_votes",default=False,type=bool)
            owner_id = request.form.get("owner_id",default=None,type=int)
            post_id = request.form.get("post_id",default=None,type=int)
            choix_ids = [ele[0] for ele in request.form.getlist("choix_ids",type=list)]
        except ValueError:
            return render_template("page_message.html",message="Un paramètre de votre requète a été mal-formé :/",texte_btn="Revenir à l'acceuil",lien="/mes_sondages")

        
        # check if every params are not None, if post belongs to the current user, if each choice belongs to the right post and if post exists
        if (choix != None) and (post_header != None) and (anon_votes != None) and (choix_ids != []) and (not False in [db.choix_exists(owner_id,post_id,c,check_id=True) for c in choix_ids]) and (db.post_exists(post_id)) and (owner_id == current_user.id):
            
            #remove any empty string
            choix = list(filter(None, choix.split("/")))              
            
            if len(choix) == 1:
                return render_template("page_message.html",message="Veuillez remplir le champ des choix comme ceci : choix1/choix2/choix3....",texte_btn="Refaire le sondage",btn_url=request.url)

            #everything is okay
            else:
                db.update_anon_votes(post_id,anon_votes)
                
                for c_id,c_text in zip(choix_ids,choix):
                    db.update_choix(post_id,c_id,c_text)
                
                db.update_post_header(post_id,post_header)
        
                return redirect("/mes_sondages")

@app.route("/supprimer_sondage",methods=["POST"])
@login_required
def supprimer_sondage():
    # post pour supprimer le sondage
    if request.method == "POST":
        
        if (request.form.get("post_author",default=None) != None) and (request.form.get("post_id",default=None) != None):

            # check if post_id is an int
            try:
                post_id = request.form.get("post_id",type=int)
            except ValueError:
                return render_template("page_message.html",message="Un paramètre de votre requète a été mal-formé :/",texte_btn="Revenir à l'acceuil",lien="/home")
            
            
            username = request.form.get("post_author")            
            
            # vérifie que le post existe bien et appartient bien à l'utilisateur connecté
            if (current_user.name == username) and  (db.post_exists(post_id)):
                db.delete_post(current_user.id,post_id)
                return render_template("page_message.html",message="Sondage supprimé !",texte_btn="Revenir à l'acceuil",lien="/home")
            else:
                return render_template("page_message.html",message="Vous demandez la suppression d'un sondage qui n'est pas le votre :/",texte_btn="Revenir à l'acceuil",lien="/home")

        else:
            return render_template("page_message.html",message="Le sondage que vous demandez n'est malheureusement pas/plus disponible :/",texte_btn="Revenir à l'acceuil",lien="/home")
    

@app.route("/profil",methods=["GET"])
@login_required
def profil():
    
    try:
        user_id = request.args.get("user_id",default=None,type=int)
    except ValueError:
        return render_template("page_message.html",message="Un paramètre de votre requète a été mal-formé :/",texte_btn="Revenir à l'acceuil",lien="/home")
    
    
    
    if (user_id != None) and (db.user_exists(user_id)):
        # generate html from markdown
        with open(f"static/users_profile_md/{user_id}.md","r") as f:
            
            md = markdown(f.read(),output_format="html")
            f.close()
        # sanitize generated html
        md = Sanitizer().sanitize(md)

        
        return render_template("profile.html",md=md,username=current_user.name,user_id=user_id,is_following=(user_id in db.get_following(current_user.id)))
    else:
        return render_template("page_message.html",message="Cet utilisateur n'existe pas :/",texte_btn="Revenir à l'acceuil",lien="/login")

@app.route("/edit_profil",methods=["GET","POST"])
@login_required
def edit_profil():
    
    
        if request.method == "GET":
            # generate html from markdown
            with open(f"static/users_profile_md/{current_user.id}.md","r") as f:
                md = f.read()
                f.close()
            
            return render_template("profile_settings.html",md=md,username=current_user.name,user_id=current_user.id)
        
        elif request.method == "POST":
            
            # generate html from markdown
            with open(f"static/users_profile_md/{current_user.id}.md","w") as f:
                md = request.form.get("profile_desc",default="",type=str)
                f.write(md.replace("\n",""))
                f.close()
            
            return redirect("edit_profil")

@app.errorhandler(404)
def page_not_found(error):
    return redirect(url_for("home"))





if __name__ == "__main__":
    
    if not path.exists("database.db"):
        db.__init_db()
    
    app.run(host="0.0.0.0",port="80",debug=True)
