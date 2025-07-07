from flask import Flask, render_template, flash, redirect, url_for, session, request
from wtforms import Form, StringField, PasswordField, TextAreaField, validators
from passlib.hash import sha256_crypt
from functools import wraps
import sqlite3
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

DATABASE = "database.db"

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "logged_in" in session:
            return f(*args, **kwargs)
        else:
            flash("Bu Sayfayı Görüntülemek İçin Lütfen Giriş Yapın!", "danger")
            return redirect(url_for("login"))
    return decorated_function

class RegisterForm(Form):
    name = StringField("İsim-Soyisim", validators=[validators.Length(min=4)])
    username = StringField("Kullanıcı Adı", validators=[validators.Length(min=2, max=25)])
    email = StringField("E-Mail", validators=[validators.Email()])
    password = PasswordField("Parola", validators=[
        validators.DataRequired(),
        validators.EqualTo("confirm", message="Parolalar uyuşmuyor.")
    ])
    confirm = PasswordField("Parola Doğrula")

class LoginForm(Form):
    username = StringField("Kullanıcı")
    password = PasswordField("Parola")

class ArticleForm(Form):
    title = StringField("Konu Başlığı", validators=[validators.Length(min=5, max=100)])
    content = TextAreaField("Konu İçeriği", validators=[validators.Length(min=10)])

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/articles")
def articles():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM articles")
    articles = cursor.fetchall()
    return render_template("articles.html", articles=articles) if articles else render_template("articles.html")

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM articles WHERE author = ?", (session["author"],))
    articles = cursor.fetchall()
    return render_template("dashboard.html", articles=articles) if articles else render_template("dashboard.html")

# Kayıt Olma İşlemi

@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm(request.form)
    if request.method == "POST" and form.validate():
        name = form.name.data
        username = form.username.data
        email = form.email.data
        password = sha256_crypt.hash(form.password.data)

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users(name, email, username, password) VALUES (?, ?, ?, ?)", (name, email, username, password))
        conn.commit()

        flash("Başarıyla kayıt oldunuz.", "success")
        return redirect(url_for("login"))

    return render_template("register.html", form=form)

# Login İşlemi

@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm(request.form)
    if request.method == "POST":
        username = form.username.data
        password_entered = form.password.data

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        data = cursor.fetchone()

        if data:
            real_password = data["password"]
            if sha256_crypt.verify(password_entered, real_password):
                flash("Başarıyla Giriş Yapıldı", "success")
                session["logged_in"] = True
                session["username"] = username
                session["author"] = username
                return redirect(url_for("index"))
            else:
                flash("Yanlış Parola", "danger")
        else:
            flash("Böyle Bir Kullanıcı Bulunmuyor", "danger")
    return render_template("login.html", form=form)

# Profil Sekmesi

@app.route("/profil/<string:username>")
def profil(username):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    if not user:
        flash("Kullanıcı bulunamadı", "danger")
        return redirect(url_for("index"))
    cursor.execute("SELECT * FROM articles WHERE author = ?", (username,))
    articles = cursor.fetchall()    

    return render_template("profil.html", user=user, articles=articles)

# Logout İşlemi

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


def article(id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM articles WHERE id = ?", (id,))
    article = cursor.fetchone()
    return render_template("article.html", article=article) if article else render_template("article.html")

from datetime import datetime  

# Konu Ekleme

@app.route("/addarticle", methods=["GET", "POST"])
@login_required
def addarticle():
    form = ArticleForm(request.form)
    if request.method == "POST" and form.validate():
        title = form.title.data
        content = form.content.data
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO articles(title, author, content, created_date) VALUES (?, ?, ?, ?)",
                       (title, session["username"], content, now))  
        conn.commit()
        flash("Konu Başarıyla Eklendi", "success")
        return redirect(url_for("dashboard"))
    return render_template("addarticle.html", form=form)

# Konu Silme

@app.route("/delete/<string:id>")
@login_required
def delete(id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM articles WHERE author = ? AND id = ?", (session["username"], id))
    result = cursor.fetchone()
    if result:
        cursor.execute("DELETE FROM articles WHERE id = ?", (id,))
        conn.commit()
        flash("Konu silindi", "success")
    else:
        flash("Böyle bir konu yok veya bu işleme yetkiniz yok", "danger")
    return redirect(url_for("dashboard"))

# Konu Güncelleme

@app.route("/edit/<string:id>", methods=["GET", "POST"])
@login_required
def update(id):
    conn = get_db()
    cursor = conn.cursor()
    if request.method == "GET":
        cursor.execute("SELECT * FROM articles WHERE id = ? AND author = ?", (id, session["username"]))
        article = cursor.fetchone()
        if article:
            form = ArticleForm()
            form.title.data = article["title"]
            form.content.data = article["content"]
            return render_template("update.html", form=form)
        else:
            flash("Böyle bir konu yok veya bu işleme yetkiniz yok", "danger")
            return redirect(url_for("index"))
    else:
        form = ArticleForm(request.form)
        newTitle = form.title.data
        newContent = form.content.data
        cursor.execute("UPDATE articles SET title = ?, content = ? WHERE id = ?", (newTitle, newContent, id))
        conn.commit()
        flash("Konu başarıyla güncellendi", "success")
        return redirect(url_for("dashboard"))
    
# Yorum Yapma
from datetime import datetime

@app.route("/article/<string:id>", methods=["GET", "POST"])
def article(id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM articles WHERE id = ?", (id,))
    article = cursor.fetchone()

    if not article:
        flash("Böyle bir konu bulunamadı", "danger")
        return redirect(url_for("articles"))

    # Yorum gönderildiyse ve kullanıcı giriş yaptıysa
    if request.method == "POST" and "logged_in" in session:
        content = request.form.get("comment")

        if not content or content.strip() == "":
            flash("Yorum içeriği boş olamaz!", "warning")
            return redirect(url_for("article", id=id))

        author = session["username"]
        created_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            INSERT INTO comments (article_id, author, content, created_date)
            VALUES (?, ?, ?, ?)
        """, (id, author, content.strip(), created_date))
        conn.commit()
        flash("Yorum başarıyla eklendi", "success")
        return redirect(url_for("article", id=id))

    elif request.method == "POST":
        flash("Yorum yapmak için giriş yapmalısınız.", "danger")
        return redirect(url_for("login"))

    # Yorumları göster
    cursor.execute("SELECT * FROM comments WHERE article_id = ? ORDER BY id DESC", (id,))
    comments = cursor.fetchall()

    return render_template("article.html", article=article, comments=comments)

# Yorum Silme

@app.route("/delete_comment/<int:comment_id>", methods=["POST"])
@login_required
def delete_comment(comment_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM comments WHERE id = ?", (comment_id,))
    comment = cursor.fetchone()

    if not comment:
        flash("Yorum bulunamadı.", "danger")
        return redirect(request.referrer or url_for("index"))

    if comment["author"] != session["username"]:
        flash("Bu yorumu silmeye yetkiniz yok.", "danger")
        return redirect(request.referrer or url_for("index"))

    # Yorumu sil
    cursor.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
    conn.commit()
    flash("Yorum başarıyla silindi.", "success")
    return redirect(request.referrer or url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
