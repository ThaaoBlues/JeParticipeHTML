from multiprocessing import context
from flask import *
from flask_dance.contrib.google import make_google_blueprint, google
from flask_login import login_required, login_user, logout_user, LoginManager, UserMixin, current_user



# Somewhere in webapp_example.py, before the app.run for example
import os 
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = '1'


app = Flask(__name__)
app.secret_key = "oui"
blueprint = make_google_blueprint(
    client_id="70544792963-f5cguhvv1nr4rm4c4ka4e1k7cmu6vnut.apps.googleusercontent.com",
    client_secret="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",
    scope=["email","profile"]
)
app.register_blueprint(blueprint, url_prefix="/login")


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'google.login'


class User(UserMixin):
    
    
    def __init__(self, name="[anonymous]", id=0, active=True,gender="autre"):
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
    

@app.route("/")
def index():
    
    #normal redirect
    if not google.authorized:
        return redirect(url_for("google.login"))
    
    
    #user login from google
    resp = google.get("/oauth2/v2/userinfo")
    
    
    if not resp.ok:
        redirect("/")
    else:
        username = resp.json()["name"].replace(" ","_")
        email = resp.json()
        return "You are username : {uname} email :{email} on Google".format(uname=username,email=email)



if __name__ == "__main__":
    app.run(debug=True,port=80)