import os
import secrets
from PIL import Image
from flask import render_template, url_for, flash, redirect, request
from sqlalchemy.orm import session

from mulagi import app, db, bcrypt, mail
from mulagi.forms import RegistrationForm, LoginForm, UpdateAccountForm, messageForm, contactsForm, RequestResetForm, ResetPasswordForm
from mulagi.models import User, message, phone_number , load_user
from flask_login import login_user, current_user, logout_user, login_required
from flask_mail import Message


epi = [
    {
        'name': 'surveyApp',
        'year': '2020',

    },

]


@app.route("/")
def main():
    return render_template('landing.html', epi=epi)

@app.route("/home")
@login_required
def home():

    page = request.args.get('page', 1, type=int)
    posts = message.query.order_by(message.date_posted.desc()).paginate(page=page, per_page=5)


    return render_template('home.html', posts=posts)

@app.route("/contacts")
@login_required
def contacts():
    page = request.args.get('page', 1, type=int)
    posts = phone_number.query.order_by(phone_number.date_posted.desc()).paginate(page=page, per_page=5)


    return render_template('phone_view.html', posts=posts)


@app.route("/about")
def about():
    return render_template('about.html', title='About')


@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)


@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:

        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', title='Login', form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('main'))


def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/profile_pics', picture_fn)

    output_size = (125, 125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)

    return picture_fn


@app.route("/account", methods=['GET', 'POST'])
@login_required
def account():
    form = UpdateAccountForm()
    if form.validate_on_submit():
        if form.picture.data:
            picture_file = save_picture(form.picture.data)
            current_user.image_file = picture_file
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Your account has been updated!', 'success')
        return redirect(url_for('account'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
    image_file = url_for('static', filename='profile_pics/' + current_user.image_file)
    return render_template('account.html', title='Account',
                           image_file=image_file, form=form)


@app.route("/message/new", methods=['GET', 'POST'])
@login_required
def new_message():
    form = messageForm()
    if form.validate_on_submit():
        status = "PENDING"
        post = message(status=status, text=form.text.data, author=current_user)
        db.session.add(post)
        db.session.commit()
        flash('your message was SENT!', 'success')
        return redirect(url_for('home'))
    return render_template('create_message.html', title='New message',
                           form=form, legend='New message')

@app.route("/contacts/new", methods=['GET', 'POST'])
@login_required
def new_contacts():
    form = contactsForm()
    if form.validate_on_submit():
        post = phone_number(phone=form.phone.data, author=current_user)
        db.session.add(post)
        db.session.commit()
        flash('new contact has been created!', 'success')
        return redirect(url_for('contacts'))
    return render_template('create_phone.html', title='New contact',
                           form=form, legend='New contact')

@app.route("/user/<string:username>")
def user_posts(username):
    page = request.args.get('page', 1, type=int)
    user = User.query.filter_by(username=username).first_or_404()
    posts = message.query.filter_by(author=user)\
        .order_by(message.date_posted.desc())\
        .paginate(page=page, per_page=5)
    return render_template('home.html', posts=posts, user=user)

@app.route("/number/<string:username>")
def user_contacts(username):
    page = request.args.get('page', 1, type=int)
    user = User.query.filter_by(username=username).first_or_404()
    numbers = phone_number.query.filter_by(author=user)\
        .order_by(phone_number.date_posted.desc())\
        .paginate(page=page, per_page=5)
    return render_template('phone_view.html', posts=numbers, user=user)


def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message('Password Reset Request',
                  sender='noreply@demo.com',
                  recipients=[user.email])
    msg.body = f'''To reset your password, visit the following link:
{url_for('reset_token', token=token, _external=True)}
If you did not make this request then simply ignore this email and no changes will be made.
'''
    mail.send(msg)


@app.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        send_reset_email(user)
        flash('An email has been sent with instructions to reset your password.', 'info')
        return redirect(url_for('login'))
    return render_template('reset_request.html', title='Reset Password', form=form)


@app.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    user = User.verify_reset_token(token)
    if user is None:
        flash('That is an invalid or expired token', 'warning')
        return redirect(url_for('reset_request'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user.password = hashed_password
        db.session.commit()
        flash('Your password has been updated! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('reset_token.html', title='Reset Password', form=form)