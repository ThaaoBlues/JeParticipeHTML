from post import Post
from passlib.handlers.sha2_crypt import sha256_crypt
from flask import Flask,url_for, render_template,request,redirect,send_from_directory,jsonify
import database_handler
from flask_login import login_required, login_user, logout_user, LoginManager, UserMixin, current_user
from random import choices, randint
from os import path
from markdown import markdown
from html_sanitizer import Sanitizer
from time import sleep
from multiprocessing import Process, freeze_support
from os import remove

# csrf protection
from flask_wtf.csrf import CSRFProtect

#init flask app
app = Flask(__name__)


db = database_handler.DataBase()

app.config["DOWNLOAD_FOLDER"] = "./static/downloads"
app.config['CUSTOM_LOGO_PATH'] = "./logo"

# sessions and login manager stuff

login_manager = LoginManager()

login_manager.init_app(app)

app.secret_key = "".join(choices("1234567890°+AZERTYUIOP¨£µQSDFGHJKLM%WXCVBN?./§<>azertyuiopqsdfghjklmwxcvbn",k=1024))


csrf = CSRFProtect(app)



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

    @property
    def is_authenticated(self):
        return True
    
    def get_id(self):
        return self.id

@login_manager.user_loader
def user_loader(user_id):
    
    # prevent multiples refresh from one ip to make server crash
    while True:
        try:
            user = User(name=db.get_user_name(user_id),id=user_id,gender=db.get_gender(user_id))
            return user
        except Exception as e:
            print("exception",e)
            
            sleep(2)


        
        
@login_manager.unauthorized_handler
def unauthorized_handler():
    return redirect(url_for("login"))

@app.route("/")
def accueil():
    
    return redirect(url_for("login"))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template("login.html")
    
    
    elif(request.form.get('username',default=None) != None ) and (request.form.get('password',default=None) != None):
    
        if request.form.get('username',default=None) != None:
            
            
            username = db.sanitize(request.form.get('username'))

            if (not db.username_exists(username)) or (username == "anonyme"):
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
                return render_template("page_message.html",message="Un paramètre de votre requète a été mal-formé :/",texte_btn="Revenir à l'accueil",lien="/home")
            
                        
            if (db.post_exists(post_id)):
                post = db.get_post(post_id)

                post = Post(post["header"],post["choix"],db.get_user_name(post["owner_id"]),post["owner_id"],id=post["post_id"],results=db.get_results(post["post_id"]),anon_votes=post["anon_votes"],vote=vote,post_type=post["publication_type"])

                return render_template("share_post.html",post = post)
                
            else:
                return render_template("page_message.html",message="Cet utilisateur n'existe pas :/",texte_btn="Revenir à l'accueil",lien="/home")

        else:
            return render_template("page_message.html",message="Le sondage que vous demandez n'est malheureusement pas/plus disponible ou n'a jamais existé ou un paramètre de votre requète a été mal-formé :/ :/",texte_btn="Revenir à l'accueil",lien="/home")
    
    
    elif request.method == "POST":
                
        
        req = dict(request.get_json())

        
        if("choix" in req.keys()) and ("post_id" in req.keys()) and ("author_id" in req.keys()):


            choix = str(req["choix"])
            
            # check if post_id is an int
            try:
                post_id = int(req["post_id"])
                author_id = int(req["author_id"])
            except ValueError:
                return jsonify({"erreur","requête mal formée"})
            
            if (db.choix_exists(author_id,post_id,choix)):
                if ("email" in req.keys()):
                    email = req["email"]
                    
                    if (email in db.get_tirage_participants(post_id)["emails"]) or (email in db.get_tirage_participants(post_id)["usernames"]):
                        return jsonify({"erreur":"adresse email deja utilisée"})
                    
                    try:
                        if current_user.is_authenticated:
                            db.add_vote(current_user.id,author_id,choix,post_id,current_user.gender)
                        else:
                            db.add_vote(1,author_id,choix,post_id,"",email=email,anon_vote=True)
                    except Exception as e:
                        print(e)
                        
                else:
                    if current_user.is_authenticated:
                        db.add_vote(current_user.id,author_id,choix,post_id,current_user.gender)
                    else:
                        db.add_vote(1,author_id,choix,post_id,"",anon_vote=True)

                    
                return jsonify({"succes":"requête validée"})
            
            else:
                return jsonify({"erreur","requête mal formée"})
                    
        else:
            return jsonify({"erreur","requête mal formée"})
                
@app.route('/home',methods=['GET'])
@login_required
def home():
    
    # prevent user from spamming requests
    while True:
        try:
            sondages = db.generate_tl(current_user.id)
            break
        except Exception as e:
            print(e)
            logout_user()
            return redirect("/")
    return render_template("home.html",username = current_user.name,sondages = sondages)

@app.route("/recherche",methods=["GET"])
@login_required
def recherche():    
    
    # get request
    if request.args.get("req",default=None) != None:
        req = db.sanitize(request.args.get("req"))

        profils = []
        following = db.get_following(current_user.id)
        
        profils = db.match_users(req)
        
        error = profils == []

        return render_template("search.html",following = following,profils=profils,error=error,username=current_user.name)
    else:
        return render_template("search.html",profils=[],req="",username=current_user.name)


@app.route("/creer_publication",methods=["GET","POST"])
@login_required
def sondage_form():
    
    
    if request.method == "GET":
        return render_template("create_post.html",username=current_user.name)
    
    
    elif request.method == "POST":
        
        post_header = request.form.get("post_header",default=None)
        choix = request.form.get("choix",default=None)
        post_type = request.form.get("publication_type",default="sondage")
        
        try:
            anon_votes = request.form.get("anon_votes",default=False,type=bool)
        except ValueError:
            return render_template("page_message.html",message="Un paramètre de votre requète a été mal-formé :/",texte_btn="Revenir à l'accueil",lien="/home")

        
        
        if (choix != None) and (post_header != None) and (anon_votes != None) and (post_type in db.publication_types):
            
            #remove any empty string
            choix = list(filter(None, choix.split("/")))
            # tries to not transmit XSS
            choix = [db.sanitize(c,text=True) for c in choix]
            
            if (len(choix) == 1) and (post_type=="sondage"):
                return render_template("page_message.html",message="Veuillez remplir le champ des choix comme ceci : choix1/choix2/choix3....",texte_btn="Refaire le sondage",btn_url="/creer_sondage")
                        
            db.add_post(current_user.id,{"header":post_header,"choix":choix,"anon_votes":anon_votes,"publication_type":post_type})
            
            return render_template("page_message.html",message="Sondage publié ! Prenez un café et attendez les retours ;)",texte_btn="Revenir à l'accueil",lien="/home")

            
        else:
            return render_template("page_message.html",message="Veuillez remplir la totalité des champs.",texte_btn="Refaire le sondage",btn_url="/creer_sondage")


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect("/")


@app.route('/register',methods=["POST"])
def register():
    
    
    
    if (request.form.get("username",None) != None) and (request.form.get("password",None) != None) and (request.form.get("type",default=None).lower() in db.users_types) and (request.form.get("genre",default=None).lower().replace(" ","_") in db.gender_types) and (request.form.get("email",default=None) != None):
        
        username = db.sanitize(request.form.get("username"))
        email = db.sanitize(request.form.get("email",str),text=True)
        
        if db.email_exists(email):
            return render_template("page_message.html",message="Un compte utilise déjà cette adresse email :/ Ne vous inquiétez pas, vous avez assez d'imagination pour en trouver un autre ;)",texte_btn="Revenir à la page d'enregistrement",lien="/login")
        
        gender = request.form.get("genre",type=str).lower().replace(" ","_")
        
        # if user already exists, abort and return a nice message
        if db.username_exists(username):
            return render_template("page_message.html",message="Ce nom d'utilisateur existe déjà :/ Ne vous inquiétez pas, vous avez assez d'imagination pour en trouver un autre ;)",texte_btn="Revenir à la page d'enregistrement",lien="/login")
        
        password=sha256_crypt.hash(request.form.get("password"))
        
        user_id = db.register_user(username=username,gender=gender,email=email,password=password,type=request.form.get("type").lower(),franceconnect=True)
        
        # login user after registration
        user = User(name=username,id=user_id,gender=db.get_gender(user_id)) 
        login_user(user,remember=True)
        
        return redirect("/home")
        
        
    else:
        return render_template("page_message.html",message="Un problème est survenu lors de votre enregistrement :/",texte_btn="Revenir à l'accueil",lien="/")
    

@app.route("/stats",methods=["GET","POST"])
@login_required
def stats():
    
    # page de stats et possibilité de delete le sondage
    
    if request.method == "GET":
    
        if (request.args.get("post_id",default=None) != None):
            
            # check if post_id is an int
            try:
                post_id = request.args.get("post_id",type=int)
            except ValueError:
                return render_template("page_message.html",message="Un paramètre de votre requète a été mal-formé :/",texte_btn="Revenir à l'accueil",lien="/home")
            
            if not db.post_exists(post_id):
                return render_template("page_message.html",message="Un paramètre de votre requète a été mal-formé :/",texte_btn="Revenir à l'accueil",lien="/home")
            
            post_dict = db.get_post(post_id)
            
            if post_dict["owner_id"] != current_user.id:
                return render_template("page_message.html",message="Vous demandez les statistiques d'un sondage qui n'est pas le votre :/",texte_btn="Revenir à l'accueil",lien="/home")

            
            
            
            
            match post_dict["publication_type"]:
                
                
                case "sondage":
                    chart_type = request.args.get("chart_type",default="pie",type=str)
            
                    if not chart_type in ["bar","pie","doughnut","polarArea"]:
                        return render_template("page_message.html",message="Un paramètre de votre requète a été mal-formé :/",texte_btn="Revenir à l'accueil",lien="/home")
                    

                    
                    stats = db.get_post_stats(post_id)
                    
                    post = Post(post_dict["header"],post_dict["choix"],db.get_user_name(post_dict["owner_id"]),post_dict["owner_id"],results=db.get_results(post_id),vote=db.has_already_voted(current_user.id,post_id),id=post_id,stats=stats)
                                                    
                    resultats = db.get_results(post_id)
                    
                    # to make the charts
                    colors = [ f"rgb({randint(0, 255)},{randint(0, 255)},{randint(0, 255)})" for _ in range(len(resultats))]

                    genders = {"list":[g for g in db.gender_types],"colors":[ f"rgb({randint(0, 255)},{randint(0, 255)},{randint(0, 255)})" for _ in range(len(db.gender_types)+1)]}
                            
                    # choix without special chars to put as variable names
                    sanitized_choix = {}
                    for c in post_dict["choix"]:
                        sanitized_choix[c] = db.sanitize(c)
                    
                    return render_template("stats.html",username=current_user.name,post = post,resultats=resultats,resultats_values=list(resultats.values()),chart_colors=colors,genders=genders,sanitized_choix=sanitized_choix,chart_type=chart_type)
                    
                
                case "tirage":
                    
                    participants = db.get_tirage_participants(post_id)
                    
                    return render_template("tirage_stats.html",username=current_user.name,participants = participants)
                
                case _ :
                    return jsonify({"erreur":"type de publication non supporté."})
            
            
        else:
            return render_template("page_message.html",message="Le sondage que vous demandez n'est malheureusement pas/plus disponible :/",texte_btn="Revenir à l'accueil",lien="/home")
    
    elif request.method == "POST":
        
        
        try:    
            post_id = request.form.get("post_id",default=None,type=int)
        except ValueError:
            return render_template("page_message.html",message="Un paramètre de votre requète a été mal-formé :/",texte_btn="Revenir à l'accueil",lien="/home")
            
    
        # post exists ?
        if (post_id != None) and (db.post_exists(post_id)):
            
            
            # post belongs to the connected user ?
            
            if (db.get_post(post_id)["owner_id"] == current_user.id):
                
                filename = db.generate_csv(post_id)
                
                Process(target=remove_zip,args=(filename,)).start()
                
                return send_from_directory(app.config["DOWNLOAD_FOLDER"],filename,environ=request.environ,download_name="resultats_sondage.zip")

            else:
                return render_template("page_message.html",message="Le sondage demandé ne vous appartiens pas :/",texte_btn="Revenir à l'accueil",lien="/home")
        else:
            return render_template("page_message.html",message="Le sondage que vous demandez n'est malheureusement pas/plus disponible :/",texte_btn="Revenir à l'accueil",lien="/home")

    
    
@app.route("/mes_publications",methods=["GET","POST"])
@login_required
def mes_sondages():
    sondages = db.generate_tl(current_user.id,self_only=True)
        
    return render_template("my_posts.html",username = current_user.name,sondages = sondages)

@app.route("/parametres_publication",methods=["GET","POST"])
@login_required
def parametres_sondage():
    
    
    if request.method == "GET":
        
        # check request args
        try:
            post_id = request.args.get("post_id",type=int,default=None)
            owner_id = request.args.get("owner_id",type=int,default=None)
        except ValueError:
            return render_template("page_message.html",message="Un paramètre de votre requète a été mal-formé :/",texte_btn="Revenir à l'accueil",lien="/mes_sondages")

        if (post_id == None) or (owner_id == None):
            return render_template("page_message.html",message="Un paramètre de votre requète a été mal-formé :/",texte_btn="Revenir à l'accueil",lien="/mes_sondages")
        
        post = db.get_post(post_id)

        #check if post exists and belongs to the current user
        if db.post_exists(post_id) and (owner_id == current_user.id) and (post["owner_id"] == current_user.id):
            post = Post(post["header"],post["choix"],db.get_user_name(post["owner_id"]),post["owner_id"],id=post["post_id"],anon_votes=post["anon_votes"],choix_ids=db.get_choix_ids(post["post_id"]),archive=post["archived"],post_type=post["publication_type"])
            
            return render_template("post_settings.html",post=post,username=current_user.name)
        
        # else throw an error message
        else:
            
            return render_template("page_message.html",message="Le sondage que vous demandez n'est malheureusement pas/plus disponible pour vous ou n'a jamais existé",texte_btn="Revenir à l'accueil",lien=request.url)


            
    
    elif request.method == "POST":

        post_header = request.form.get("post_header",default=None)
        choix = request.form.get("choix",default=None)
        post_type = request.form.get("publication_type",default=None)
        # check if everything is from the right type
        try:
            anon_votes = request.form.get("anon_votes",default=False,type=bool)
            owner_id = request.form.get("owner_id",default=None,type=int)
            post_id = request.form.get("post_id",default=None,type=int)
            choix_ids = [ele[0] for ele in request.form.getlist("choix_ids",type=list)]
            archive = request.form.get("archive",default=False,type=bool)
        except ValueError:
            print("VALUE ERROR")
            return render_template("page_message.html",message="Un paramètre de votre requète a été mal-formé :/",texte_btn="Revenir à l'accueil",lien="/mes_sondages")

        if not (post_type in db.publication_types):
            return jsonify({"error":"wrong post type"})
        
        
        
        # check if every params are not None, if post belongs to the current user, if each choice belongs to the right post and if post exists
        if (choix != None) and (post_header != None) and (anon_votes != None) and (choix_ids != "") and (archive != None) and (db.post_exists(post_id)) and (owner_id == current_user.id):
            
            #remove any empty string
            choix = list(filter(None, choix.split("/")))              
            
            if (len(choix) == 1) and (post_type=="sondage"):
                return render_template("page_message.html",message="Veuillez remplir le champ des choix comme ceci : choix1/choix2/choix3....",texte_btn="Refaire le sondage",btn_url=request.url)

            #everything is okay
            else:
                db.update_anon_votes(post_id,anon_votes)
                
                for c_id,c_text in zip(choix_ids,choix):
                    db.update_choix(post_id,c_id,c_text)
                
                db.update_post_header(post_id,post_header)
                db.update_post_archive_state(post_id,archive)

                return redirect(f"/parametres_publication?owner_id={current_user.id}&post_id={post_id}")
        
        # manque un paramètre de form 
        else:
            return render_template("page_message.html",message="Un paramètre de votre requète a été mal-formé :/",texte_btn="Revenir à l'accueil",lien="/mes_sondages")


@app.route("/supprimer_publication",methods=["POST"])
@login_required
def supprimer_sondage():
    # post pour supprimer le sondage
    if request.method == "POST":
        
        if (request.form.get("post_author",default=None) != None) and (request.form.get("post_id",default=None) != None):

            # check if post_id is an int
            try:
                post_id = request.form.get("post_id",type=int)
            except ValueError:
                return render_template("page_message.html",message="Un paramètre de votre requète a été mal-formé :/",texte_btn="Revenir à l'accueil",lien="/home")
            
            
            username = request.form.get("post_author")            
            
            # vérifie que le post existe bien et appartient bien à l'utilisateur connecté
            if (current_user.name == username) and  (db.post_exists(post_id)):
                db.delete_post(current_user.id,post_id)
                return render_template("page_message.html",message="Votre publication a été supprimée !",texte_btn="Revenir à l'accueil",lien="/home")
            else:
                return render_template("page_message.html",message="Vous demandez la suppression d'un sondage qui n'est pas le votre :/",texte_btn="Revenir à l'accueil",lien="/home")

        else:
            return render_template("page_message.html",message="Le sondage que vous demandez n'est malheureusement pas/plus disponible :/",texte_btn="Revenir à l'accueil",lien="/home")

@app.route("/profil",methods=["GET"])
@login_required
def profil():
    
    try:
        user_id = request.args.get("user_id",default=None,type=int)
    except ValueError:
        return render_template("page_message.html",message="Un paramètre de votre requète a été mal-formé :/",texte_btn="Revenir à l'accueil",lien="/home")
    

    
    if (user_id != None) and (db.user_exists(user_id)):
        # generate html from markdown
        with open(f"static/users_profile_md/{user_id}.md","r") as f:
            
            md = markdown(f.read(),output_format="html")
            f.close()
        # sanitize generated html
        md = Sanitizer().sanitize(md)

        
        return render_template("profile.html",md=md,username=current_user.name,user_id=user_id,is_following=(user_id in db.get_following(current_user.id)),target_username=db.get_user_name(user_id),posts_count=db.get_posts_count(user_id))
    else:
        return render_template("page_message.html",message="Cet utilisateur n'existe pas :/",texte_btn="Revenir à l'accueil",lien="/home")

@app.route("/edit_profil",methods=["GET","POST"])
@login_required
def edit_profil():
    
    
        if request.method == "GET":
            # generate html from markdown
            with open(f"static/users_profile_md/{current_user.id}.md","r") as f:
                md = f.read()
                f.close()
            
            return render_template("profile_settings.html",md=md,username=current_user.name,user_id=current_user.id,is_private=db.is_private(current_user.id),email=db.get_email(current_user.id))
        
        elif request.method == "POST":
            
                
            # generate html from markdown
            with open(f"static/users_profile_md/{current_user.id}.md","w") as f:
                md = request.form.get("profile_desc",default="",type=str)
                f.write(md.replace("\n",""))
                f.close()
        
            
            # change is an user is private or not, a private user have a follow request section
            try:
                status = request.form.get("is_private",default=False,type=bool)
            except ValueError:
                return render_template("page_message.html",message="Un paramètre de votre requète a été mal-formé :/",texte_btn="Revenir à l'accueil",lien="/edit_profil")
            db.set_private_status(current_user.id,status)
            
            email = request.form.get("email",default=None)
            
            if db.email_exists(email):
                return render_template("page_message.html",message="Un compte utilise déjà cette adresse email :/ Ne vous inquiétez pas, vous avez assez d'imagination pour en trouver un autre ;)",texte_btn="Revenir en arrière",lien="/edit_profil")
        
            
            if email:
                db.update_email(current_user.id,email)
            else:
                return jsonify({"error":"no email in form"})
        
            return redirect("edit_profil")


@app.route("/mes_abonnes",methods=["GET"])
@login_required
def mes_abonnes():
    """page où une timeline de tout ses abonnées apparaît avec la possibilité de les retirer

    Returns:
        [type]: [description]
    """
    
    followers_id = db.get_followers(current_user.id)
    
    # don't display the self-follow
    followers_id.pop(followers_id.index(current_user.id))

    profils = [db.get_user_info(user_id) for user_id in followers_id]
    
    return render_template("followers.html",profils=profils,following=db.get_following(current_user.id),username=current_user.name)


@app.route("/mes_abonnements",methods=["GET"])
@login_required
def mes_abonnements():
    """page avec une timeline de tout ses abonnements, pour pouvoir se désabonner facilement

    Returns:
        [type]: [description]
    """
    
    following_id = db.get_following(current_user.id)
    
    # don't display the self-follow
    following_id.pop(following_id.index(current_user.id))

    profils = [db.get_user_info(user_id) for user_id in following_id]
    
    return render_template("following.html",profils=profils,following=db.get_following(current_user.id),username=current_user.name)
    

@app.route("/mes_demandes_dabonnement",methods=["GET","POST"])
@login_required
def mes_demandes():
    """page où une timeline apparait avec les profils ayant demandés à s'abonner,
    possibilité d'accepter ou de rejeter

    Returns:
        [type]: [description]
    """
    
    if not db.is_private(current_user.id):
        return render_template("page_message.html",message="Votre compte n'est pas en mode privé, cette section ne vous sert à rien ;)",texte_btn="revenir à l'accueil",lien="/home")
    else:
        return render_template("follow_requests.html",profils=db.generate_requests_tl(current_user.id),following=db.get_following(current_user.id),username=current_user.name)

@app.route("/action/<action>",methods=["POST"])
@login_required
def action(action):
            
    req = dict(request.get_json())
    
    match action:
        
        case "delete_account":
            user_id = current_user.id  
            logout_user()
            db.delete_user(user_id)
            return jsonify({"succès":"opération effecutée"})

        
        
        case "add_vote":
            
            if("choix" in req.keys()) and ("post_id" in req.keys()) and ("author_id" in req.keys()):


                choix = str(req["choix"])
                
                # check if post_id is an int
                try:
                    post_id = int(req["post_id"])
                    author_id = int(req["author_id"])
                except ValueError:
                    return jsonify({"erreur","requête mal formée"})
                
                if (db.choix_exists(author_id,post_id,choix)):
                    
                    db.add_vote(current_user.id,author_id,choix,post_id,current_user.gender)
                    return jsonify({"succes":"requête validée"})
                
                else:
                    return jsonify({"erreur","requête mal formée"})
                      
            else:
                return jsonify({"erreur","requête mal formée"})
        
        
        case "follow":
            
        
            if ("user_id" in req.keys()):
           
                
                # don't forget to check if the parameter is of the right type
                try:
                    user_id = int(req["user_id"])
                except ValueError:
                    return jsonify({"erreur","requête mal formée"})                
                
                if not (current_user.id in db.get_followers(user_id)):
                    db.follow(current_user.id,user_id,is_request=db.is_private(user_id))

                    return jsonify({"succes":"requête validée"})
                
                else:
                    return jsonify({"erreur":"utilisateur déjà ajouté à vos abonnements"})

            else:
                return jsonify({"erreur","requête mal formée"})

            
        case "unfollow":
            if ("user_id" in req.keys()):
           
           
                # don't forget to check if the parameter is of the right type
                try:
                    user_id = int(req["user_id"])
                except ValueError:
                    return jsonify({"erreur","requête mal formée"})
                                                   
                if (current_user.id in db.get_followers(user_id)) and (db.user_exists(user_id)):

                    db.unfollow(current_user.id,user_id)
                    return jsonify({"succes":"requête validée"})
                
                else:
                    return jsonify({"erreur":"utilisateur non dans vos abonnements"})
            
            else:
                return jsonify({"erreur","requête mal formée"})                

        case "deny_follow_request":
            
            if ("link_id" in req.keys()):
                try:
                    link_id = int(req["link_id"])
                except:
                    return jsonify({"erreur","requête mal formée"})
                
                
                if db.is_link_related_to(current_user.id,link_id):
                    db.deny_follow_request(link_id)
                    return jsonify({"succes":"requête validée"})

                else:
                    return jsonify({"erreur","requête mal formée"})
                
            else:
                return jsonify({"erreur","requête mal formée"})

        case "accept_follow_request":
            if ("link_id" in req.keys()):
                try:
                    link_id = int(req["link_id"])
                except:
                    return jsonify({"erreur","requête mal formée"})
                
                if db.is_link_related_to(current_user.id,link_id):
                    db.accept_follow_request(link_id)
                    return jsonify({"succes":"requête validée"})

                else:
                    return jsonify({"erreur","requête mal formée"})
                
                
            else:
                return jsonify({"erreur","requête mal formée"})
                    

        case "kick_follower":
            if ("user_id" in req.keys()):
           
                # don't forget to check if the parameter is of the right type
                try:
                    user_id = int(req["user_id"])
                except ValueError:
                    return jsonify({"erreur","requête mal formée"})
                
                 
                if(db.user_exists(user_id) and (user_id in db.get_followers(current_user.id))):
                    db.unfollow(user_id,current_user.id)
                    return jsonify({"succes":"requête validée"})
                
                else:
                    return jsonify({"erreur":"utilisateur non dans vos abonnements"})
            
            else:
                return jsonify({"erreur","requête mal formée"})       
        
        case _:
            return jsonify({"erreur","requête mal formée"})


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(path.join(app.root_path,"logo"),'favicon.png', mimetype='image/vnd.microsoft.icon')

# logo static data
@app.route('/logo/<path:filename>')
def custom_static(filename):
    return send_from_directory(app.config['CUSTOM_LOGO_PATH'], filename)

@app.errorhandler(404)
def page_not_found(error):
    return redirect(url_for("home"))

def remove_zip(filename):
    """to remove zip file after being sent to user

    Args:
        filename ([type]): [description]
    """
    sleep(60)
    
    remove(f"static/downloads/{filename}")





if __name__ == "__main__":
    
    freeze_support()
    
    if not path.exists("database.db"):
        db.__init_db()
    
    app.run(host="0.0.0.0",port="80",debug=True)
