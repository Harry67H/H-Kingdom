from flask import Flask, request, redirect, session, render_template_string, url_for, send_from_directory, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import os
from PIL import Image
import datetime
import random

# === Setup ===
app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
db = SQLAlchemy(app)

# Ensure upload folders exist
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])
VIDEO_FOLDER = 'videos'
if not os.path.exists(VIDEO_FOLDER):
    os.makedirs(VIDEO_FOLDER)
app.config['VIDEO_FOLDER'] = VIDEO_FOLDER

# === Models ===
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    channel = db.relationship('Channel', backref='owner', uselist=False)
    subscriptions = db.relationship('Subscription', backref='user', lazy=True)

class Channel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    icon = db.Column(db.String(200), nullable=True)
    banner = db.Column(db.String(200), nullable=True)  # New banner field
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    videos = db.relationship('Video', backref='channel', lazy=True)

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class LikeDislike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    value = db.Column(db.Integer, nullable=False)  # 1 = like, -1 = dislike

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(500), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True)

class Subscription(db.Model):  # New model for subscriptions
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'))

with app.app_context():
    db.create_all()

# === Helpers ===
THEME_CSS = {
    "light": {"bg": "#ffffff", "fg": "#111111", "muted": "#555555", "panel": "#f3f3f3", "accent": "#2b7cff"},
    "dark": {"bg": "#0f1115", "fg": "#e8eef8", "muted": "#9aa6bf", "panel": "#111418", "accent": "#4ea1ff"},
    "gold": {"bg": "#fffaf0", "fg": "#2b2b2b", "muted": "#7a5a2a", "panel": "#fff3d6", "accent": "#c79b00"},
    "cyan": {"bg": "#e8fbff", "fg": "#032a2e", "muted": "#0f6b73", "panel": "#dff7f9", "accent": "#08a6b5"}
}

def current_theme():
    t = session.get('theme', 'light')
    if t not in THEME_CSS:
        t = 'light'
    return t

def theme_style_block():
    t = THEME_CSS[current_theme()]
    return f"""
    <style>
    :root {{
        --bg: {t['bg']};
        --fg: {t['fg']};
        --muted: {t['muted']};
        --panel: {t['panel']};
        --accent: {t['accent']};
    }}
    body {{ background: var(--bg); color: var(--fg); font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
    a {{ color: var(--accent); text-decoration: none; }}
    .topbar {{ display:flex; gap:10px; align-items:center; margin-bottom:12px; }}
    .btn {{ background:var(--panel); border:1px solid var(--muted); padding:6px 10px; border-radius:6px; cursor:pointer; }}
    .panel {{ background: var(--panel); padding:12px; border-radius:8px; border:1px solid var(--muted); }}
    textarea {{ width:100%; }}
    </style>
    """

def user_channel_name(user_id):
    user = User.query.get(user_id)
    if not user:
        return None
    if user.channel:
        return user.channel.name
    return user.email

# --- Theme route ---
@app.route('/set_theme/<name>')
def set_theme(name):
    if name not in THEME_CSS:
        name = 'light'
    session['theme'] = name
    ref = request.referrer or url_for('index')
    return redirect(ref)

# === Routes ===
# --- Homepage with search & recommended section ---
@app.route('/', methods=['GET', 'POST'])
def index():
    theme_block = theme_style_block()
    user_id = session.get('user_id')
    query = request.form.get('query', '') if request.method == 'POST' else ''
    if query:
        videos = Video.query.filter(Video.title.contains(query)).order_by(Video.uploaded_at.desc()).all()
    else:
        videos = Video.query.order_by(Video.uploaded_at.desc()).limit(50).all()

    topbar = f"""
    <div class='topbar'>
    <strong>H Kingdom</strong> | <a class='btn' href='/channels'>Channels</a> 
    {"<a class='btn' href='/upload_video'>Upload</a>" if user_id and User.query.get(user_id).channel else ""}
    {"<a class='btn' href='/logout'>Logout</a>" if user_id else "<a class='btn' href='/login'>Login</a> <a class='btn' href='/create_account'>Sign up</a>"}
    <form method='post' style='margin-left:auto; display:flex; gap:6px;'>
        <input type='text' name='query' placeholder='Search...' value='{query}'>
        <input class='btn' type='submit' value='Search'>
    </form>
    <div style='margin-left:auto'>Theme: 
        <a class='btn' href='/set_theme/light'>Light</a>
        <a class='btn' href='/set_theme/dark'>Dark</a>
        <a class='btn' href='/set_theme/gold'>Gold</a>
        <a class='btn' href='/set_theme/cyan'>Cyan</a>
    </div>
    </div>
    """
    html = theme_block + topbar + "<h1>Recent Videos</h1>"

    if not videos:
        html += "<p>No videos yet.</p>"
    else:
        for v in videos:
            ch = Channel.query.get(v.channel_id)
            html += "<div class='panel' style='margin-bottom:12px;'>"
            html += f"<h3>{v.title} <small style='color:var(--muted)'>by <a href='/channel/{ch.id}'>{ch.name}</a></small></h3>"
            html += f"<video width='480' controls><source src='/videos/{v.filename}' type='video/mp4'>Your browser does not support the video tag.</video><br>"
            html += f"<small style='color:var(--muted)'>Uploaded: {v.uploaded_at.strftime('%Y-%m-%d %H:%M:%S')}</small>"
            html += "</div>"

    # Personalized recommended videos for logged-in users
    if user_id:
        user = User.query.get(user_id)
        recommended = []
        subscribed_channel_ids = [s.channel_id for s in Subscription.query.filter_by(user_id=user_id)]
        if subscribed_channel_ids:
            recommended = Video.query.filter(Video.channel_id.in_(subscribed_channel_ids)).order_by(Video.uploaded_at.desc()).limit(5).all()
        else:  # Random videos if no subscriptions
            recommended = Video.query.order_by(db.func.random()).limit(5).all()

        if recommended:
            html += "<h2>Recommended for you</h2>"
            for v in recommended:
                ch = Channel.query.get(v.channel_id)
                html += "<div class='panel' style='margin-bottom:12px;'>"
                html += f"<h4>{v.title} <small style='color:var(--muted)'>by <a href='/channel/{ch.id}'>{ch.name}</a></small></h4>"
                html += f"<video width='320' controls><source src='/videos/{v.filename}' type='video/mp4'></video>"
                html += "</div>"

    return html

# --- Login with forgot password button ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    theme_block = theme_style_block()
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email, password=password).first()
        if user:
            session['user_id'] = user.id
            if user.channel:
                return redirect(url_for('channel_page', channel_id=user.channel.id))
            return redirect(url_for('create_channel'))
        else:
            return "Invalid login! <a href='/login'>Try again</a>"
    return theme_block + render_template_string('''
    <div class='topbar'>
        <strong>H Kingdom</strong>
        <div style='margin-left:auto'>
            <a class='btn' href='/set_theme/light'>Light</a>
            <a class='btn' href='/set_theme/dark'>Dark</a>
            <a class='btn' href='/set_theme/gold'>Gold</a>
            <a class='btn' href='/set_theme/cyan'>Cyan</a>
        </div>
    </div>
    <div class='panel'>
        <h2>Login</h2>
        <form method="post">
            Email: <input type="email" name="email" required><br><br>
            Password: <input type="password" name="password" required><br><br>
            <input class='btn' type="submit" value="Login">
        </form>
        <br>
        <a class='btn' href='/forgot_password'>Forgot your password?</a><br><br>
        Don't have an account? <a href="/create_account">Create one here</a>
    </div>
    ''')

# --- Forgot password (placeholder, needs email setup) ---
@app.route('/forgot_password')
def forgot_password():
    theme_block = theme_style_block()
    return theme_block + "<div class='panel'><h2>Forgot Password</h2><p>Functionality coming soon!</p></div>"

# --- Subscribe / Unsubscribe ---
@app.route('/channel/<int:channel_id>/subscribe')
def subscribe(channel_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    sub = Subscription.query.filter_by(user_id=user_id, channel_id=channel_id).first()
    if not sub:
        db.session.add(Subscription(user_id=user_id, channel_id=channel_id))
        db.session.commit()
    return redirect(url_for('channel_page', channel_id=channel_id))

@app.route('/channel/<int:channel_id>/unsubscribe')
def unsubscribe(channel_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    sub = Subscription.query.filter_by(user_id=user_id, channel_id=channel_id).first()
    if sub:
        db.session.delete(sub)
        db.session.commit()
    return redirect(url_for('channel_page', channel_id=channel_id))

# --- Channel page with banner and subscribe button ---
@app.route("/channel/<int:channel_id>")
def channel_page(channel_id):
    theme_block = theme_style_block()
    c = Channel.query.get_or_404(channel_id)
    user_id = session.get('user_id')
    html = theme_block + f"<h1>{c.name}</h1>"

    if c.banner:
        html += f"<img src='/uploads/{c.banner}' width='100%' height='200' style='object-fit:cover;'><br><br>"

    if c.icon:
        html += f"<img src='/uploads/{c.icon}' width='150' height='150'><br>"

    # Subscribe button
    if user_id and user_id != c.user_id:
        sub = Subscription.query.filter_by(user_id=user_id, channel_id=c.id).first()
        if sub:
            html += f"<a class='btn' href='/channel/{c.id}/unsubscribe'>Unsubscribe</a><br><br>"
        else:
            html += f"<a class='btn' href='/channel/{c.id}/subscribe'>Subscribe</a><br><br>"

    html += "<h2>Videos</h2>"
    if not c.videos:
        html += "<p>No videos yet!</p>"
    else:
        for v in c.videos:
            likes = LikeDislike.query.filter_by(video_id=v.id, value=1).count()
            dislikes = LikeDislike.query.filter_by(video_id=v.id, value=-1).count()
            html += "<div class='panel' style='margin-bottom:18px;'>"
            html += f"<h3>{v.title}</h3>"
            html += f"<video width='480' controls><source src='/videos/{v.filename}' type='video/mp4'></video><br>"
            html += f"👍 {likes} | 👎 {dislikes}"
            html += "</div>"

    # Upload link if owner
    if user_id and c.user_id == user_id:
        html += "<a class='btn' href='/upload_video'>Upload a Video</a>"

    return html

# --- Serve uploads & videos ---
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/videos/<filename>')
def uploaded_video(filename):
    return send_from_directory(app.config['VIDEO_FOLDER'], filename)

# --- Run App ---
if __name__ == '__main__':
    app.run(debug=True)
