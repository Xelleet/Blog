import json
import os.path
import secrets

import flask
from werkzeug.security import generate_password_hash, check_password_hash

from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from flask import Flask, render_template, request, redirect, url_for, flash, session as flask_session
from werkzeug.utils import secure_filename, send_from_directory

app = Flask(__name__)
app.secret_key = '4f6b89def1878fc36f41258ac7dd77d9'
UPLOAD_FOLDER = 'uploads/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
DATABASE_URL = 'sqlite:///usersdatabase.db'
engine = create_engine(DATABASE_URL)
Base = declarative_base()


class Account(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False, unique=True)
    email = Column(String(120), nullable=False, unique=True)
    password = Column(String(200), nullable=False)
    profile_picture = Column(String(200))


class Article(Base):
    __tablename__ = 'articles'
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    content = Column(String, nullable=False)
    user_id = Column(Integer, nullable=False)

class Comment(Base):
    __tablename__ = 'comments'
    id = Column(Integer, primary_key=True)
    content = Column(String, nullable=False)
    article_id = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=False)

    def __repr__(self):
        return f'<Comment {self.id} by User {self.user_id}>'

class Note(Base):
    __tablename__ = 'notes'
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=True)
    content = Column(String, nullable=True)
    user_id = Column(Integer, nullable=False)


Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


def save_user(user):
    try:
        with open('user.json', 'a') as f:
            json.dump(user, f)
            f.write('\n')
    except Exception as e:
        print(f"Error saving user data: {e}")


@app.route('/')
def home():
    session = Session()
    articles = session.query(Article).all()
    session.close()
    return render_template("home.html", articles=articles)


@app.route('/foundling', methods=['GET', 'POST'])
def foundling():
    user_id = flask_session.get('account_id')
    session = Session()
    if not user_id:
        flash('Пожалуйста, войдите в систему, чтобы добавить статью')
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']

        new_article = Article(title=title, content=content, user_id=user_id)
        session.add(new_article)
        session.commit()
        return redirect(url_for('article', article_id=new_article.id))

    return render_template('foundling.html')

@app.route('/note', methods = ['GET', 'POST'])
def add_note():
    user_id = flask_session.get('account_id')
    session = Session()
    if not user_id:
        flash('Пожалуйста, войдите в систему, чтобы добавить заметку')
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']

        new_note = Note(title=title, content=content, user_id=user_id)
        session.add(new_note)
        session.commit()
        return redirect(url_for('note', note_id=new_note.id))

    return render_template('add_note.html')

@app.route('/about')
def about():
    return render_template("about.html")


@app.route('/services')
def services():
    return render_template("services.html")


@app.route('/contacts')
def contacts():
    return render_template("contacts.html")


@app.route('/article/<int:article_id>')
def article(article_id):
    session = Session()

    article = session.query(Article).filter_by(id=article_id).first()

    if not article:
        flash('Article not found')
        return redirect(url_for('home'))

    author = session.query(Account).filter_by(id=article.user_id).first()
    comments = session.query(Comment).filter_by(article_id=article_id).all()

    if request.method == 'POST':
        comments_content = request.form['content']
        user_id = flask_session.get('account_id')

        if not user_id:
            flash('You need to be logged in to post a comment')
            session.close()
            return redirect(url_for('login'))

        new_comment = Comment(content=comments_content, user_id=user_id, article_id=article_id)
        session.add(new_comment)
        session.commit()
        flash('Your comment has been posted')
        session.close()
        return redirect(url_for('article', article_id=article_id))

    session.close()
    return render_template('article.html', article=article, author=author, comments=comments)

@app.route('/note/<int:note_id>')
def note(note_id):
    session = Session()
    note = session.query(Note).filter_by(id=note_id).first()
    if not note:
        flash('Note is not found')
        return redirect(url_for('home'))

    author = session.query(Note).filter_by(id=note.user_id).first()
    session.close()
    return render_template('note.html', note=note, author=author)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == "POST":
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Passwords do not match')
            return redirect(url_for('register'))

        session = Session()
        if session.query(Account).filter((Account.name == username) | (Account.email == email)).first():
            flash('Username or email already exists')
            session.close()
            return redirect(url_for('register'))

        new_user = Account(name=username, email=email, password=generate_password_hash(password))
        session.add(new_user)
        session.commit()
        session.close()
        flash('Registration successful')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/account', methods=['GET', 'POST'])
def account():
    user_id = flask_session.get('account_id')
    session = Session()
    notes = session.query(Note).all()
    if not user_id:
        flash('Please log in first')
        return redirect(url_for('login'))

    session = Session()
    user = session.query(Account).filter_by(id=user_id).first()
    if not user:
        flash('User not found')
        session.close()
        return redirect(url_for('login'))

    if request.method == 'POST':
        file = request.files.get('profile_picture')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            user.profile_picture = file_path
            session.commit()
            flash('Profile picture uploaded successfully')

    session.close()
    return render_template('account.html', user=user, notes=notes)


def allowed_file(filename):
    """Проверяет, разрешён ли формат файла."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']
        session = Session()
        account = session.query(Account).filter_by(name=username).first()
        session.close()

        if account and check_password_hash(account.password, password):
            flask_session['account_id'] = account.id
            flash('Login successful')
            return redirect(url_for('account'))
        else:
            flash('Invalid username or password')

    return render_template('login.html')

@app.route('/logout')
def logout():
    flask.session.pop('account_id', None)
    flash('Вы вышли из системы')
    return redirect(url_for('home'))

@app.route('/delete_note/<int:note_id>')
def delete_note(note_id):
    session = Session()
    note = session.query(Note).get(note_id)
    if note:
        session.delete(note)
        session.commit()
    return redirect(url_for('account'))

if __name__ == "__main__":
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)
