from flask import Flask, request, redirect, session, render_template_string, url_for, send_from_directory, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import os
from PIL import Image
import datetime

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

class Channel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    icon = db.Column(db.String(200), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

Channel.videos = db.relationship('Video', backref='channel', lazy=True)

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

with app.app_context():
    db.create_all()

# === Helpers ===
THEME_CSS = {
    "light": {
        "bg": "#ffffff",
        "fg": "#111111",
        "muted": "#555555",
        "panel": "#f3f3f3",
        "accent": "#2b7cff"
    },
    "dark": {
        "bg": "#0f1115",
        "fg": "#e8eef8",
        "muted": "#9aa6bf",
        "panel": "#111418",
        "accent": "#4ea1ff"
    },
    "gold": {
        "bg": "#fffaf0",
        "fg": "#2b2b2b",
        "muted": "#7a5a2a",
        "panel": "#fff3d6",
        "accent": "#c79b00"
    },
    "cyan": {
        "bg": "#e8fbff",
        "fg": "#032a2e",
        "muted": "#0f6b73",
        "panel": "#dff7f9",
        "accent": "#08a6b5"
    }
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
    # return to previous page if possible
    ref = request.referrer or url_for('index')
    return redirect(ref)

# === Routes ===
@app.route('/')
def index():
    # Homepage: show recent videos across channels (front page)
    videos = Video.query.order_by(Video.uploaded_at.desc()).limit(50).all()
    theme_block = theme_style_block()
    user_id = session.get('user_id')
    topbar = f"""
      <div class='topbar'>
        <strong>H Kingdom</strong> |
        <a class='btn' href='/channels'>Channels</a>
        {"<a class='btn' href='/upload_video'>Upload</a>" if user_id and User.query.get(user_id).channel else ""}
        {"<a class='btn' href='/logout'>Logout</a>" if user_id else "<a class='btn' href='/login'>Login</a> <a class='btn' href='/create_account'>Sign up</a>"}
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
    return html

# --- Create Account ---
@app.route('/create_account', methods=['GET', 'POST'])
def create_account():
    theme_block = theme_style_block()
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if User.query.filter_by(email=email).first():
            return "Email already exists! <a href='/login'>Login here</a>"
        user = User(email=email, password=password)
        db.session.add(user)
        db.session.commit()
        session['user_id'] = user.id
        return redirect(url_for('create_channel'))
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
        <h2>Create Account</h2>
        <form method="post">
            Email: <input type="email" name="email" required><br><br>
            Password: <input type="password" name="password" required><br><br>
            <input class='btn' type="submit" value="Create Account">
        </form>
        <br>
        Already have an account? <a href="/login">Login here</a>
        </div>
    ''')

# --- Login ---
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
        Don't have an account? <a href="/create_account">Create one here</a>
        </div>
    ''')

# --- Logout ---
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- Create Channel ---
@app.route('/create_channel', methods=['GET', 'POST'])
def create_channel():
    theme_block = theme_style_block()
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    user = User.query.get(user_id)
    if user.channel:
        return redirect(url_for('channel_page', channel_id=user.channel.id))

    if request.method == 'POST':
        name = request.form['name']
        file = request.files.get('icon')
        icon_filename = None
        if file and file.filename:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            img = Image.open(file)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img.save(file_path)
            icon_filename = filename
        channel = Channel(name=name, icon=icon_filename, owner=user)
        db.session.add(channel)
        db.session.commit()
        return redirect(url_for('channel_page', channel_id=channel.id))

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
        <h2>Create Channel</h2>
        <form method="post" enctype="multipart/form-data">
            Channel Name: <input type="text" name="name" required><br><br>
            Channel Icon: <input type="file" name="icon" accept=".png,.jpg,.jpeg,.bmp,.tiff,.gif"><br><br>
            <input class='btn' type="submit" value="Create Channel">
        </form>
        </div>
    ''')

# --- List all channels ---
@app.route("/channels")
def list_channels():
    theme_block = theme_style_block()
    channels = Channel.query.all()
    html = theme_block + """
    <div class='topbar'>
      <strong>H Kingdom</strong>
      <div style='margin-left:auto'>
        <a class='btn' href='/set_theme/light'>Light</a>
        <a class='btn' href='/set_theme/dark'>Dark</a>
        <a class='btn' href='/set_theme/gold'>Gold</a>
        <a class='btn' href='/set_theme/cyan'>Cyan</a>
      </div>
    </div>
    <h1>All Channels</h1><ul>
    """
    for c in channels:
        html += f"""
        <li style='margin-bottom:20px;' class='panel'>
            <a href='/channel/{c.id}' style='font-size:20px;'>{c.name}</a><br>
            {"<img src='/uploads/" + c.icon + "' width='100' height='100'>" if c.icon else ""}
        </li>
        """
    html += "</ul>"
    return html

# --- Serve uploads & videos ---
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/videos/<filename>')
def uploaded_video(filename):
    return send_from_directory(app.config['VIDEO_FOLDER'], filename)

# --- Upload Video (only to your own channel) ---
@app.route('/upload_video', methods=['GET', 'POST'])
def upload_video():
    theme_block = theme_style_block()
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    user = User.query.get(user_id)
    if not user.channel:
        return "You must create a channel first! <a href='/create_channel'>Make one here</a>"

    if request.method == 'POST':
        title = request.form['title']
        file = request.files.get('video')
        if not file or not file.filename:
            return "No video file uploaded!"
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['VIDEO_FOLDER'], filename)
        file.save(file_path)
        video = Video(title=title, filename=filename, channel=user.channel)
        db.session.add(video)
        db.session.commit()
        return redirect(url_for('channel_page', channel_id=user.channel.id))

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
        <h2>Upload Video to Your Channel</h2>
        <form method="post" enctype="multipart/form-data">
            Title: <input type="text" name="title" required><br><br>
            Video File: <input type="file" name="video" accept="video/*" required><br><br>
            <input class='btn' type="submit" value="Upload Video">
        </form>
        </div>
    ''')

# --- Like/Dislike ---
@app.route("/video/<int:video_id>/like")
def like_video(video_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    existing = LikeDislike.query.filter_by(user_id=user_id, video_id=video_id).first()
    if existing:
        existing.value = 1
    else:
        db.session.add(LikeDislike(user_id=user_id, video_id=video_id, value=1))
    db.session.commit()
    return redirect(url_for('channel_page', channel_id=Video.query.get(video_id).channel_id))

@app.route("/video/<int:video_id>/dislike")
def dislike_video(video_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    existing = LikeDislike.query.filter_by(user_id=user_id, video_id=video_id).first()
    if existing:
        existing.value = -1
    else:
        db.session.add(LikeDislike(user_id=user_id, video_id=video_id, value=-1))
    db.session.commit()
    return redirect(url_for('channel_page', channel_id=Video.query.get(video_id).channel_id))

# --- Comments: add, edit, delete ---
@app.route("/video/<int:video_id>/comment", methods=["POST"])
def comment_video(video_id):
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    content = request.form.get('content','').strip()
    if content:
        db.session.add(Comment(content=content, user_id=user_id, video_id=video_id))
        db.session.commit()
    return redirect(url_for('channel_page', channel_id=Video.query.get(video_id).channel_id))

@app.route("/comment/<int:comment_id>/edit", methods=["GET", "POST"])
def edit_comment(comment_id):
    c = Comment.query.get_or_404(comment_id)
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    if c.user_id != user_id:
        return "You are not allowed to edit this comment.", 403

    if request.method == 'POST':
        content = request.form.get('content','').strip()
        if content:
            c.content = content
            c.updated_at = datetime.datetime.utcnow()
            db.session.commit()
        return redirect(url_for('channel_page', channel_id=Video.query.get(c.video_id).channel_id))

    # GET => show edit form
    theme_block = theme_style_block()
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
          <h3>Edit Comment</h3>
          <form method="post">
            <textarea name="content" rows="4" required>{{content}}</textarea><br>
            <input class='btn' type="submit" value="Save">
          </form>
        </div>
    ''', content=c.content)

@app.route("/comment/<int:comment_id>/delete", methods=["POST"])
def delete_comment(comment_id):
    c = Comment.query.get_or_404(comment_id)
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    if c.user_id != user_id:
        return "You are not allowed to delete this comment.", 403
    vid_channel = Video.query.get(c.video_id).channel_id
    db.session.delete(c)
    db.session.commit()
    return redirect(url_for('channel_page', channel_id=vid_channel))

# --- Channel Page (videos, likes, comments) ---
@app.route("/channel/<int:channel_id>")
def channel_page(channel_id):
    theme_block = theme_style_block()
    c = Channel.query.get_or_404(channel_id)
    html = theme_block + """
      <div class='topbar'>
        <strong>H Kingdom</strong>
        <a class='btn' href='/channels'>Channels</a>
        <div style='margin-left:auto'>
          <a class='btn' href='/set_theme/light'>Light</a>
          <a class='btn' href='/set_theme/dark'>Dark</a>
          <a class='btn' href='/set_theme/gold'>Gold</a>
          <a class='btn' href='/set_theme/cyan'>Cyan</a>
        </div>
      </div>
      <h1>{name}</h1>
    """.format(name=c.name)

    if c.icon:
        html += f"<img src='/uploads/{c.icon}' width='150' height='150'><br>"

    html += "<h2>Videos</h2>"
    if not c.videos:
        html += "<p>No videos yet!</p>"
    else:
        for v in c.videos:
            likes = LikeDislike.query.filter_by(video_id=v.id, value=1).count()
            dislikes = LikeDislike.query.filter_by(video_id=v.id, value=-1).count()
            comments = Comment.query.filter_by(video_id=v.id).order_by(Comment.created_at.asc()).all()

            html += "<div class='panel' style='margin-bottom:18px;'>"
            html += f"<h3>{v.title}</h3>"
            html += f"<small style='color:var(--muted)'>Uploaded: {v.uploaded_at.strftime('%Y-%m-%d %H:%M:%S')}</small><br>"
            html += f"<video width='480' controls><source src='/videos/{v.filename}' type='video/mp4'>Your browser does not support the video tag.</video><br>"
            html += f"<a class='btn' href='/video/{v.id}/like'>👍 Like ({likes})</a> "
            html += f"<a class='btn' href='/video/{v.id}/dislike'>👎 Dislike ({dislikes})</a>"

            # Comment form (only logged-in users)
            user_id = session.get('user_id')
            html += "<h4>Comments</h4>"
            if user_id:
                html += f"""
                    <form method="post" action="/video/{v.id}/comment">
                        <textarea name="content" rows="2" required></textarea><br>
                        <input class='btn' type="submit" value="Add Comment">
                    </form>
                """
            else:
                html += "<p><a href='/login'>Login</a> to comment.</p>"

            if not comments:
                html += "<p>No comments yet!</p>"
            else:
                for com in comments:
                    author = User.query.get(com.user_id)
                    author_name = author.channel.name if author and author.channel else (author.email if author else "Unknown")
                    html += "<div style='border-top:1px solid var(--muted); padding-top:6px; margin-top:6px;'>"
                    html += f"<b>{author_name}</b> <small style='color:var(--muted)'>{com.created_at.strftime('%Y-%m-%d %H:%M:%S')}{(' (edited '+com.updated_at.strftime('%Y-%m-%d %H:%M:%S')+')') if com.updated_at else ''}</small>"
                    html += f"<p>{com.content}</p>"

                    # edit/delete buttons if current user is comment owner
                    if user_id and com.user_id == user_id:
                        html += f"""
                        <form style='display:inline' method='get' action='/comment/{com.id}/edit'>
                          <button class='btn' type='submit'>Edit</button>
                        </form>
                        <form style='display:inline' method='post' action='/comment/{com.id}/delete' onsubmit="return confirm('Delete comment?');">
                          <button class='btn' type='submit'>Delete</button>
                        </form>
                        """
                    html += "</div>"

            html += "</div>"

    # If viewer is channel owner, show upload link
    user_id = session.get('user_id')
    if user_id:
        user = User.query.get(user_id)
        if user and user.channel and user.channel.id == channel_id:
            html += "<br><a class='btn' href='/upload_video'>Upload a Video</a>"

    html += " | <a class='btn' href='/channels'>Back to Channels</a>"
    return html

# --- Run App ---
if __name__ == '__main__':
    app.run(debug=True)

