
import re
from post import Post
from passlib.handlers.sha2_crypt import sha256_crypt
from flask import Flask, session, url_for, render_template,request,redirect
import database_handler
from flask_login import login_required, login_user, logout_user, LoginManager, UserMixin, current_user
from random import choices, randint
from os import path
#init flask app
app = Flask(__name__)

db = database_handler.DataBase()


# sessions and login manager stuff

login_manager = LoginManager()

login_manager.init_app(app)

app.secret_key = "".join(choices("1234567890°+AZERTYUIOP¨£µQSDFGHJKLM%WXCVBN?./§<>azertyuiopqsdfghjklmwxcvbn",k=1024))


class User(UserMixin):
    
    
    def __init__(self, name="", id=0, active=True,gender="autre"):
        self.name = name
        self.id = id
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
    
    user = User(name=db.get_user_name(user_id),id=user_id,gender=db.get_gender(user_id))
    
    return user

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
                return render_template("page_message.html",message="Un paramètre de votre requète a été mal-formé :/",texte_btn="Revenir à l'acceuil",lien="/login")
            
                        
            if (db.post_exists(post_id)):
                post = db.get_post(owner_id,post_id)

                post = Post(post["header"],post["choix"],db.get_user_name(post["owner_id"]),post["owner_id"],id=post["post_id"],results=db.get_results(post["owner_id"],post["post_id"]),anon_votes=post["anon_votes"],vote=vote)

                return render_template("share_post.html",post = post)
                
            else:
                return render_template("page_message.html",message="Cet utilisateur n'existe pas :/",texte_btn="Revenir à l'acceuil",lien="/login")

        else:
            return render_template("page_message.html",message="Le sondage que vous demandez n'est malheureusement pas/plus disponible ou n'a jamais existé ou un paramètre de votre requète a été mal-formé :/ :/",texte_btn="Revenir à l'acceuil",lien="/login")
    
    
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
        
    sondages = db.generate_tl(current_user.id)
        
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

    req = db.sanitize(request.args.get("req"))

    if request.method == "POST":
        if (request.form.get("username",default=None) != None) and (request.form.get("action",default=None) != None):
           
            # don't forget to remove all spacial chars
            user = db.sanitize(request.form.get("username"))
            
            if request.form.get("action") == "unfollow":
                
                db.unfollow(current_user.id,user)
                db.del_follower(db.get_user_id(user),current_user.name)
                
            elif request.form.get("action") == "follow":
                
                db.follow(current_user.id,user)
                db.add_follower(db.get_user_id(user),current_user.name)
            
        return redirect(f"/recherche?req={req}")
    
    
    
    elif request.args.get("req",default=None) != None:
        profils = []
        following = db.get_following(current_user.id)
        
        profils = db.match_users(req)

        return render_template("search.html",following = following,profils=profils)
    else:
        return render_template("search.html",profils=[],req=req)


@app.route("/creer_sondage",methods=["GET","POST"])
@login_required
def sondage_form():
    
    
    if request.method == "GET":
        return render_template("create_post.html")
    
    
    elif request.method == "POST":
        
        post_header = request.form.get("post_header",default=None)
        choix = request.form.get("choix",default=None)
        anon_votes = request.form.get("anon_votes",default=False,type=bool)
        
        if (choix != None) and (post_header != None) and (anon_votes != None):
                        
            # tries to not transmit XSS
            choix = [db.sanitize(c,text=True) for c in choix.split("/")]
            
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


@app.route("/post",methods=["GET"])
@login_required
def post():
    
    if request.method == "GET":
        return render_template("post.html")


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
    

@app.route("/stats",methods=["GET","POST"])
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
            
            post = db.get_post(current_user.id,post_id)
            
            stats = db.get_post_stats(current_user.id,post_id)
            
            post = Post(post["header"],post["choix"],db.get_user_name(post["owner_id"]),post["owner_id"],results=db.get_results(current_user.id,post_id),vote=db.has_already_voted(current_user.id,post_id),id=post_id,stats=stats)
                    
            
            # vérifie que le post existe bien et appartient bien à l'utilisateur connecté
            if (current_user.name == username) and  (db.post_exists(post_id)):
                
                resultats = db.get_results(current_user.id,post_id)
                
                # to make the charts
                colors = [ f"rgb({randint(0, 255)},{randint(0, 255)},{randint(0, 255)})" for _ in range(len(resultats))]

                genders = {"list":[g for g in db.gender_types],"colors":[ f"rgb({randint(0, 255)},{randint(0, 255)},{randint(0, 255)})" for _ in range(len(db.gender_types)+1)]}
                          
                
                return render_template("stats.html",post = post,resultats=resultats,resultats_values=list(resultats.values()),chart_colors=colors,genders=genders)
                
            else:
                return render_template("page_message.html",message="Vous demandez les statistiques d'un sondage qui n'est pas le votre :/",texte_btn="Revenir à l'acceuil",lien="/home")

        else:
            return render_template("page_message.html",message="Le sondage que vous demandez n'est malheureusement pas/plus disponible :/",texte_btn="Revenir à l'acceuil",lien="/home")
    
    
    # post pour supprimer le sondage
    elif request.method == "POST":
        
        
        
        
        
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
    
@app.errorhandler(404)
def page_not_found(error):
    return redirect(url_for("home"))





if __name__ == "__main__":
    
    if not path.exists("database.db"):
        db.__init_db()
    
    app.run(host="0.0.0.0",port="80",debug=True)
