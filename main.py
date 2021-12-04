
from passlib.handlers.sha2_crypt import sha256_crypt
from flask import Flask, session, url_for, render_template,request,redirect
import database
from flask_login import login_required, login_user, logout_user, LoginManager, UserMixin, current_user
from random import choices
from os import path
#init flask app
app = Flask(__name__)

db = database.DataBase()


# sessions and login manager stuff

login_manager = LoginManager()

login_manager.init_app(app)

app.secret_key = "".join(choices("1234567890°+AZERTYUIOP¨£µQSDFGHJKLM%WXCVBN?./§<>azertyuiopqsdfghjklmwxcvbn",k=1024))


class User(UserMixin):
    
    
    def __init__(self, name="", id=0, active=True):
        self.name = name
        self.id = id
        self.active = active

    def is_active(self):
        # Here you should write whatever the code is
        # that checks the database if your user is active
        return self.active

    def is_anonymous(self):
        return False

    def is_authenticated(self):
        return True

@login_manager.user_loader
def user_loader(username):
    
    username = db.sanitize(username)
    
    if username not in db.get_users():
        return None

    user = User(name=username,id=db.get_user_id(username))
    
    return user

@login_manager.request_loader
def request_loader(request):
    
    if request.form.get('username',default=None) != None:
        username = db.sanitize(request.form.get('username'))
    
        if username not in db.get_users():
            return None
        
        is_auth = sha256_crypt.verify(db.sanitize(request.form.get('password')),db.get_password(username))

        user = User(name=username,id=db.get_user_id(username))        
            
        return user
    else:
        return None

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
    
    
    elif(request.form.get('username',default=None) != None ) and (request.form.get('password',default=None) != None) and (db.get_password(request.form.get("username")) != None):
    
        username = db.sanitize(request.form.get('username',default=None))
        password = request.form.get('password')
        
        # compare hashes
        if (db.get_password(username) != None) and (sha256_crypt.verify(password,db.get_password(username))):
            user = User()
            user.id = username
            login_user(user)
            
            return redirect(url_for('home'))

    else:
        return redirect(url_for("login"))

@app.route('/home',methods=['GET'])
@login_required
def home():    
    sondages = db.generate_tl(current_user.id)
        
    return render_template("home.html",username = current_user.name,sondages = sondages)



@app.route("/add_vote",methods=["POST"])
@login_required
def add_post():
    
    if (request.form.get("choix",default=None) != None) and  (request.form.get("author",default=None) != None) and  (request.form.get("post_id",default=None) != None):


        choix = request.form.get("choix")
        post_id = request.form.get("post_id",type=int)
        author = request.form.get("author")
        
        stats = db.get_posts_stats(author)
        if (choix in stats[post_id]["choix"]) and (post_id < len(stats)):
            
            db.add_vote(current_user.id,author,choix,post_id)
            
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
        
        for user in db.match_users(req):
            profils.append({"username":user["username"],"verified":db.is_verified(user["username"]),"followers":len(user["followers"]),"type": user["type"]})

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
        
        if (choix != None) and (post_header != None):
            
            # tries to not transmit XSS
            choix = [db.sanitize(c) for c in choix.split("/")]
            
            if len(choix) == 1:
                return render_template("page_message.html",message="Veuillez remplir le champ des choix comme ceci : choix1/choix2/choix3....",texte_btn="Refaire le sondage",btn_url="/creer_sondage")

            post_header.replace("{","").replace("}","")
            
            db.add_post(current_user.id,{"header":post_header,"choix":choix,"author":current_user.name})
            
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
    
    print(request.form.get("type"))
    if (request.form.get("username",None) != None) and (request.form.get("password",None) != None) and (request.form.get("type",default=None) in db.users_types):
        
        username = db.sanitize(request.form.get("username"))
        
        # if user already exists, abort and return a nice message
        if db.username_exists(username):
            return render_template("page_message.html",message="Ce nom d'utilisateur existe déjà :/ Ne vous inquiétez pas, vous avez assez d'imagination pour en trouver un autre ;)",texte_btn="Revenir à la page d'enregistrement",lien="/login")
        
        db.register_user(username,sha256_crypt.hash(request.form.get("password")),type=request.form.get("type"),franceconnect=True)
      
        return render_template("page_message.html",message="Vous avez bien été enregistré ! Clickez sur le bouton pour revenir à la page de connexion ;)",texte_btn="Revenir à l'acceuil",lien="/login")
    
    else:
        return render_template("page_message.html",message="Un problème est survenu lors de votre enregistrement :/",texte_btn="Revenir à l'acceuil",lien="/")
    

@app.errorhandler(404)
def page_not_found(error):
    return redirect(url_for("home"))



"""
if __name__ == "__main__":
    
    if not path.exists("database.csv"):
        db.__init_csv()
    
    app.run(host="0.0.0.0",port="80",debug=True)

"""