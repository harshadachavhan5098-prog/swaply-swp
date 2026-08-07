import os
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, abort, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from models import db, User, Post, Like, Comment, FriendRequest, Room, Message, Note, Notification, friendships, room_members

app = Flask(__name__)
app.config['SECRET_KEY'] = 'swaply-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///swaply.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf', 'txt', 'md', 'doc', 'docx'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        name, ext = os.path.splitext(filename)
        filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{name}{ext}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return filename
    return ''


def notify(user_id, message, link='#'):
    n = Notification(user_id=user_id, message=message, link=link)
    db.session.add(n)
    db.session.commit()


def are_friends(u1, u2):
    if u1 == u2:
        return False
    return db.session.query(friendships).filter(
        ((friendships.c.user_id == u1) & (friendships.c.friend_id == u2)) |
        ((friendships.c.user_id == u2) & (friendships.c.friend_id == u1))
    ).first() is not None


def get_friends(user):
    f1 = db.session.query(friendships.c.friend_id).filter(friendships.c.user_id == user.id)
    f2 = db.session.query(friendships.c.user_id).filter(friendships.c.friend_id == user.id)
    ids = [r[0] for r in f1.union(f2).all()]
    return User.query.filter(User.id.in_(ids)).all() if ids else []


def get_friend_ids(user_id):
    f1 = db.session.query(friendships.c.friend_id).filter(friendships.c.user_id == user_id)
    f2 = db.session.query(friendships.c.user_id).filter(friendships.c.friend_id == user_id)
    return [r[0] for r in f1.union(f2).all()]


def pending_request_between(u1, u2):
    return FriendRequest.query.filter(
        ((FriendRequest.sender_id == u1) & (FriendRequest.receiver_id == u2)) |
        ((FriendRequest.sender_id == u2) & (FriendRequest.receiver_id == u1)),
        FriendRequest.status == 'pending'
    ).first()


def is_room_member(room, user):
    if room.created_by == user.id:
        return True
    return db.session.query(room_members).filter(
        room_members.c.room_id == room.id,
        room_members.c.user_id == user.id
    ).first() is not None


def add_room_member(room_id, user_id):
    if not db.session.query(room_members).filter(
        room_members.c.room_id == room_id,
        room_members.c.user_id == user_id
    ).first():
        db.session.execute(room_members.insert().values(room_id=room_id, user_id=user_id))
        db.session.commit()


# ============ AUTH ============

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('feed'))
    return render_template('index.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('feed'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not username or not email or not password:
            flash('All fields are required.', 'danger')
        elif len(username) < 3:
            flash('Username must be at least 3 characters.', 'danger')
        elif len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
        elif password != confirm:
            flash('Passwords do not match.', 'danger')
        elif User.query.filter_by(username=username).first():
            flash('Username already taken.', 'danger')
        elif User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
        else:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('Account created! Welcome to Swaply.', 'success')
            login_user(user)
            return redirect(url_for('feed'))
    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('feed'))
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()
        if user and user.check_password(password):
            login_user(user)
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('feed'))
        flash('Invalid credentials. Please try again.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


# ============ FEED ============

@app.route('/feed')
@login_required
def feed():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template('feed.html', posts=posts)


@app.route('/post/create', methods=['POST'])
@login_required
def create_post():
    caption = request.form.get('caption', '').strip()
    skill_tags = request.form.get('skill_tags', '').strip()
    image = request.files.get('image')

    if not caption and not image:
        flash('Write a caption or add an image to create a post.', 'danger')
        return redirect(url_for('feed'))

    post = Post(
        user_id=current_user.id,
        caption=caption,
        skill_tags=skill_tags,
        image=save_upload(image) if image else ''
    )
    db.session.add(post)
    db.session.commit()
    flash('Post published!', 'success')
    return redirect(url_for('feed'))


@app.route('/post/<int:post_id>/like', methods=['POST'])
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    existing = Like.query.filter_by(user_id=current_user.id, post_id=post.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({'liked': False, 'count': len(post.likes)})
    like = Like(user_id=current_user.id, post_id=post.id)
    db.session.add(like)
    db.session.commit()
    if post.user_id != current_user.id:
        notify(post.user_id, f'{current_user.username} liked your post.', url_for('feed'))
    return jsonify({'liked': True, 'count': len(post.likes)})


@app.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    post = Post.query.get_or_404(post_id)
    content = request.form.get('content', '').strip()
    if content:
        comment = Comment(user_id=current_user.id, post_id=post.id, content=content)
        db.session.add(comment)
        db.session.commit()
        if post.user_id != current_user.id:
            notify(post.user_id, f'{current_user.username} commented on your post.', 'feed')
        flash('Comment added.', 'success')
    return redirect(url_for('feed'))


@app.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.user_id != current_user.id:
        abort(403)
    db.session.delete(post)
    db.session.commit()
    flash('Post deleted.', 'info')
    return redirect(url_for('feed'))


# ============ EXPLORE / SEARCH ============

@app.route('/explore')
@login_required
def explore():
    query = request.args.get('q', '').strip()
    skill = request.args.get('skill', '').strip()
    users = User.query.filter(User.id != current_user.id)
    if query:
        users = users.filter(
            (User.username.ilike(f'%{query}%')) |
            (User.skills_offered.ilike(f'%{query}%')) |
            (User.skills_wanted.ilike(f'%{query}%')) |
            (User.bio.ilike(f'%{query}%'))
        )
    if skill:
        users = users.filter(
            (User.skills_offered.ilike(f'%{skill}%')) |
            (User.skills_wanted.ilike(f'%{skill}%'))
        )
    users = users.order_by(User.created_at.desc()).all()
    return render_template('explore.html', users=users, query=query, skill=skill)


# ============ PROFILE ============

@app.route('/profile/<username>')
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(user_id=user.id).order_by(Post.created_at.desc()).all()
    friends = friend_list(user.id)
    is_friend = are_friends(current_user.id, user.id)
    pending = has_pending_request(current_user.id, user.id)
    return render_template('profile.html', user=user, posts=posts, friends=friends, is_friend=is_friend, pending=pending)


@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.bio = request.form.get('bio', '').strip()
        current_user.location = request.form.get('location', '').strip()
        current_user.skills_offered = request.form.get('skills_offered', '').strip()
        current_user.skills_wanted = request.form.get('skills_wanted', '').strip()
        avatar = request.files.get('avatar')
        if avatar and avatar.filename:
            current_user.avatar = save_upload(avatar)
        db.session.commit()
        flash('Profile updated!', 'success')
        return redirect(url_for('profile', username=current_user.username))
    return render_template('edit_profile.html')


# ============ FRIENDS ============

@app.route('/friends')
@login_required
def friends():
    my_friends = friend_list(current_user.id)
    pending_requests = FriendRequest.query.filter_by(receiver_id=current_user.id, status='pending').order_by(FriendRequest.created_at.desc()).all()
    sent_requests = FriendRequest.query.filter_by(sender_id=current_user.id, status='pending').order_by(FriendRequest.created_at.desc()).all()
    return render_template('friends.html', friends=my_friends, pending_requests=pending_requests, sent_requests=sent_requests)


@app.route('/friend/request/<int:user_id>', methods=['POST'])
@login_required
def send_friend_request(user_id):
    target = User.query.get_or_404(user_id)
    if target.id == current_user.id:
        flash('You cannot send a friend request to yourself.', 'warning')
        return redirect(url_for('explore'))
    if are_friends(current_user.id, target.id):
        flash('You are already friends.', 'info')
        return redirect(url_for('profile', username=target.username))
    if has_pending_request(current_user.id, target.id):
        flash('Friend request already pending.', 'info')
        return redirect(url_for('profile', username=target.username))
    req = FriendRequest(sender_id=current_user.id, receiver_id=target.id, status='pending')
    db.session.add(req)
    db.session.commit()
    notify(target.id, f'{current_user.username} sent you a friend request.', url_for('friends'))
    flash('Friend request sent!', 'success')
    return redirect(url_for('profile', username=target.username))


@app.route('/friend/accept/<int:request_id>', methods=['POST'])
@login_required
def accept_friend_request(request_id):
    req = FriendRequest.query.get_or_404(request_id)
    if req.receiver_id != current_user.id:
        abort(403)
    req.status = 'accepted'
    db.session.execute(friendships.insert().values(user_id=req.sender_id, friend_id=req.receiver_id))
    db.session.commit()
    notify(req.sender_id, f'{current_user.username} accepted your friend request.', url_for('friends'))
    flash('Friend request accepted!', 'success')
    return redirect(url_for('friends'))


@app.route('/friend/decline/<int:request_id>', methods=['POST'])
@login_required
def decline_friend_request(request_id):
    req = FriendRequest.query.get_or_404(request_id)
    if req.receiver_id != current_user.id:
        abort(403)
    req.status = 'declined'
    db.session.commit()
    flash('Friend request declined.', 'info')
    return redirect(url_for('friends'))


@app.route('/friend/remove/<int:user_id>', methods=['POST'])
@login_required
def remove_friend(user_id):
    target = User.query.get_or_404(user_id)
    db.session.execute(friendships.delete().where(
        ((friendships.c.user_id == current_user.id) & (friendships.c.friend_id == target.id)) |
        ((friendships.c.user_id == target.id) & (friendships.c.friend_id == current_user.id))
    ))
    db.session.commit()
    flash(f'Removed {target.username} from friends.', 'info')
    return redirect(url_for('friends'))


# ============ CHAT ============

@app.route('/chat')
@login_required
def chat():
    my_friends = friend_list(current_user.id)
    return render_template('chat.html', friends=my_friends)


@app.route('/chat/<int:user_id>')
@login_required
def chat_with(user_id):
    other = User.query.get_or_404(user_id)
    if not are_friends(current_user.id, other.id):
        flash('You can only chat with friends.', 'warning')
        return redirect(url_for('chat'))
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == other.id)) |
        ((Message.sender_id == other.id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.created_at.asc()).all()
    return render_template('chat.html', friends=friend_list(current_user.id), other=other, messages=messages)


@app.route('/chat/send', methods=['POST'])
@login_required
def send_message():
    receiver_id = request.form.get('receiver_id', type=int)
    content = request.form.get('content', '').strip()
    if not receiver_id or not content:
        flash('Message cannot be empty.', 'warning')
        return redirect(url_for('chat'))
    other = User.query.get_or_404(receiver_id)
    if not are_friends(current_user.id, other.id):
        flash('You can only chat with friends.', 'warning')
        return redirect(url_for('chat'))
    msg = Message(sender_id=current_user.id, receiver_id=other.id, content=content)
    db.session.add(msg)
    db.session.commit()
    notify(other.id, f'New message from {current_user.username}.', url_for('chat_with', user_id=current_user.id))
    return redirect(url_for('chat_with', user_id=other.id))


# ============ ROOMS ============

@app.route('/rooms')
@login_required
def rooms():
    all_rooms = Room.query.order_by(Room.created_at.desc()).all()
    my_rooms = [r for r in all_rooms if is_room_member(r, current_user)]
    other_rooms = [r for r in all_rooms if not is_room_member(r, current_user)]
    return render_template('rooms.html', my_rooms=my_rooms, other_rooms=other_rooms)


@app.route('/room/create', methods=['POST'])
@login_required
def create_room():
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    skill = request.form.get('skill', '').strip()
    if not name:
        flash('Room name is required.', 'danger')
        return redirect(url_for('rooms'))
    room = Room(name=name, description=description, skill=skill, created_by=current_user.id)
    db.session.add(room)
    db.session.commit()
    add_room_member(room.id, current_user.id)
    flash('Learning room created!', 'success')
    return redirect(url_for('room', room_id=room.id))


@app.route('/room/<int:room_id>')
@login_required
def room(room_id):
    room = Room.query.get_or_404(room_id)
    if not is_room_member(room, current_user):
        flash('Join this room to view its content.', 'info')
        return redirect(url_for('rooms'))
    messages = Message.query.filter_by(room_id=room.id).order_by(Message.created_at.asc()).all()
    members = room_members_list(room.id)
    return render_template('room.html', room=room, messages=messages, members=members)


@app.route('/room/<int:room_id>/join', methods=['POST'])
@login_required
def join_room(room_id):
    room = Room.query.get_or_404(room_id)
    if is_room_member(room, current_user):
        flash('You are already a member.', 'info')
    else:
        add_room_member(room.id, current_user.id)
        flash('You joined the room!', 'success')
    return redirect(url_for('room', room_id=room.id))


@app.route('/room/<int:room_id>/message', methods=['POST'])
@login_required
def send_room_message(room_id):
    room = Room.query.get_or_404(room_id)
    if not is_room_member(room, current_user):
        abort(403)
    content = request.form.get('content', '').strip()
    if content:
        msg = Message(sender_id=current_user.id, room_id=room.id, content=content)
        db.session.add(msg)
        db.session.commit()
    return redirect(url_for('room', room_id=room.id))


# ============ NOTES ============

@app.route('/notes')
@login_required
def notes():
    my_notes = Note.query.filter_by(user_id=current_user.id).order_by(Note.created_at.desc()).all()
    public_notes = Note.query.filter_by(is_public=True).filter(Note.user_id != current_user.id).order_by(Note.created_at.desc()).all()
    return render_template('notes.html', my_notes=my_notes, public_notes=public_notes)


@app.route('/note/create', methods=['POST'])
@login_required
def create_note():
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    skill = request.form.get('skill', '').strip()
    is_public = request.form.get('is_public') == 'on'
    file = request.files.get('file')
    if not title:
        flash('Note title is required.', 'danger')
        return redirect(url_for('notes'))
    note = Note(
        user_id=current_user.id,
        title=title,
        content=content,
        skill=skill,
        is_public=is_public,
        file_path=save_upload(file) if file else ''
    )
    db.session.add(note)
    db.session.commit()
    flash('Note saved!', 'success')
    return redirect(url_for('notes'))


@app.route('/note/<int:note_id>/delete', methods=['POST'])
@login_required
def delete_note(note_id):
    note = Note.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        abort(403)
    db.session.delete(note)
    db.session.commit()
    flash('Note deleted.', 'info')
    return redirect(url_for('notes'))


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ============ AI ASSISTANT ============

@app.route('/assistant')
@login_required
def assistant():
    return render_template('assistant.html')


@app.route('/assistant/ask', methods=['POST'])
@login_required
def assistant_ask():
    question = request.form.get('question', '').strip()
    if not question:
        flash('Please enter a question.', 'warning')
        return redirect(url_for('assistant'))
    answer = generate_ai_answer(question, current_user)
    return render_template('assistant.html', question=question, answer=answer)


def generate_ai_answer(question, user):
    q = question.lower()
    skills = user.skill_list(user.skills_offered) + user.skill_list(user.skills_wanted)
    skill_text = ', '.join(skills) if skills else 'not specified yet'

    if 'skill' in q or 'learn' in q or 'teach' in q:
        return (
            f"Based on your profile, you offer: {skill_text}. "
            f"To grow on Swaply, try posting about your skills in the feed, "
            f"joining learning rooms, and connecting with users who want to exchange skills. "
            f"Remember: the best way to learn is to teach!"
        )
    if 'friend' in q or 'connect' in q:
        return (
            "To make connections on Swaply, use the Explore page to search for users "
            "with matching skills. Send them a friend request, then start chatting. "
            "You can also join learning rooms to meet people with shared interests."
        )
    if 'room' in q or 'learn' in q:
        return (
            "Learning rooms are private spaces where you can collaborate with others. "
            "Create a room for a skill you want to teach, or join existing rooms. "
            "Share notes, ask questions, and exchange knowledge with members."
        )
    if 'note' in q or 'pdf' in q or 'share' in q:
        return (
            "The Notes section lets you save and share study material. "
            "You can create text notes or upload PDFs and documents. "
            "Mark notes as public to share them with the community."
        )
    if 'post' in q or 'feed' in q:
        return (
            "The feed is your space to share updates. Create posts with captions and "
            "skill tags, add images, and engage with others through likes and comments. "
            "Use skill tags to make your posts discoverable."
        )
    if 'profile' in q or 'edit' in q:
        return (
            "Your profile showcases your skills. Keep your skills_offered and skills_wanted "
            "updated so others can find you. Add a bio and location to make your profile "
            "more personal."
        )
    return (
        f"Great question! Here's a tip: your current skills are {skill_text}. "
        f"Try posting about what you're learning in the feed, or join a room to "
        f"collaborate with others. If you need specific help, ask about skills, "
        f"friends, rooms, notes, or your profile."
    )


# ============ NOTIFICATIONS ============

@app.route('/notifications')
@login_required
def notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    for n in notifs:
        n.is_read = True
    db.session.commit()
    return render_template('notifications.html', notifications=notifs)


@app.route('/notifications/unread-count')
@login_required
def unread_count():
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({'count': count})


# ============ HELPERS ============

def save_upload(file):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        name, ext = os.path.splitext(filename)
        filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{name}{ext}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return filename
    return ''


def friend_list(user_id):
    f1 = db.session.query(friendships.c.friend_id).filter(friendships.c.user_id == user_id)
    f2 = db.session.query(friendships.c.user_id).filter(friendships.c.friend_id == user_id)
    ids = [r[0] for r in f1.union(f2).all()]
    return User.query.filter(User.id.in_(ids)).all() if ids else []


def are_friends(u1, u2):
    if u1 == u2:
        return False
    return db.session.query(friendships).filter(
        ((friendships.c.user_id == u1) & (friendships.c.friend_id == u2)) |
        ((friendships.c.user_id == u2) & (friendships.c.friend_id == u1))
    ).first() is not None


def has_pending_request(u1, u2):
    return FriendRequest.query.filter(
        ((FriendRequest.sender_id == u1) & (FriendRequest.receiver_id == u2)) |
        ((FriendRequest.sender_id == u2) & (FriendRequest.receiver_id == u1)),
        FriendRequest.status == 'pending'
    ).first()


def is_room_member(room, user):
    if room.created_by == user.id:
        return True
    return db.session.query(room_members).filter(
        room_members.c.room_id == room.id,
        room_members.c.user_id == user.id
    ).first() is not None


def add_room_member(room_id, user_id):
    if not db.session.query(room_members).filter(
        room_members.c.room_id == room_id,
        room_members.c.user_id == user_id
    ).first():
        db.session.execute(room_members.insert().values(room_id=room_id, user_id=user_id))
        db.session.commit()


def room_members_list(room_id):
    rows = db.session.query(room_members.c.user_id).filter(room_members.c.room_id == room_id).all()
    ids = [r[0] for r in rows]
    return User.query.filter(User.id.in_(ids)).all() if ids else []


# ============ CONTEXT PROCESSOR ============

@app.context_processor
def inject_globals():
    unread = 0
    if current_user.is_authenticated:
        unread = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return {'unread_notifications': unread}


# ============ INIT DB ============

with app.app_context():
    db.create_all()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
