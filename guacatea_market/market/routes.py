from nis import cat
import os
import secrets
from PIL import Image
from flask import flash, redirect, render_template, url_for, request

from market import app
from market import db
from market.forms import LoginForm, RegisterForm, PurchaseItemForm, AddCartItemForm, RemoveCartItemForm, SellItemForm
from market.models.user import User
from market.models.item import Item
from market.models.cart import Cart
from flask_login import login_user, logout_user, login_required, current_user


@app.route('/')
@app.route('/home')
def home_page():
    return render_template('home.html')


@app.route('/market', methods=["GET", "POST"])
def market_page():   
    purchase_form = PurchaseItemForm()
    cart_form = AddCartItemForm()
    if request.method == "POST":
        if current_user.is_authenticated:
            # Proceso de compra
            purchased_item = request.form.get('purchased_item')
            p_item_object = Item.query.filter_by(name=purchased_item).first()
            if p_item_object:
                if current_user.can_buy(p_item_object):
                    current_user.buy(p_item_object, p_item_object.author_user)
                    flash(f"Congratulations! You purchased the '{p_item_object.name}' for {p_item_object.price}$", category='success')
                else:
                    flash(f"Unfortunately, you don't have enough money to purchase the '{p_item_object.name}'", category='danger')
            # Proceso de agregar al carrito
            added_item = request.form.get('added_item')
            a_item_object = Item.query.filter_by(name=added_item).first()
            cart = Cart.query.filter_by(userid=current_user.id).first()
            if a_item_object:
                if cart.can_add_item(a_item_object):
                    cart.add_item_to_cart(a_item_object)
                    flash(f'You added the item: {a_item_object.name} to your cart successfully', category='success')
                else:
                    flash(f"You already have the item in your cart.", category='info')
            

            return redirect(url_for('market_page'))
        else:    
            flash(f"You need to create a account or login to the page for buy any item", category='danger')
            return redirect(url_for('market_page'))

    if request.method == "GET":
        items = Item.query.filter_by(owner=None)
        return render_template("market.html",items=items, purchase_form=purchase_form, cart_form=cart_form)
        

@app.route('/register', methods=["GET", "POST"])
def register_page():
    form = RegisterForm()
    if not current_user.is_authenticated:
        if form.validate_on_submit():
            user_to_create = User(username=form.username.data,
                                email=form.email.data,
                                password=form.password_1.data,
                                )
            db.session.add(user_to_create)
            db.session.commit()
            login_user(user_to_create)
            flash(f'Account created successfully! You are now logged in as {user_to_create.username}', category='success')
            # Cuando se crea un Usuario se crea un Carrito que tiene el id del Usuario esto lo hace único
            cart_to_create = Cart(userid=user_to_create.id)
            db.session.add(cart_to_create)
            db.session.commit()
            return redirect(url_for('market_page'))

        if form.errors != {}: #If there are not errors from the validations
            for err_msg in form.errors.values():
                flash(f'There was an error with creating a user: {err_msg}', category='danger')

        return render_template('register.html', form=form)

    flash(f"You are already registered", category='info')
    return redirect(url_for('market_page'))

@app.route('/login', methods=["GET", "POST"])
def login_page():
    form = LoginForm()
    if not current_user.is_authenticated:
        if form.validate_on_submit():
            user_to_verify = User.query.filter_by(username=form.username.data).first()
            # 1ro Verifica que el usuario exista
            # 2do Verifica que la contraseña sea correcta
            if user_to_verify and user_to_verify.check_password(
                                                    attempted_password=form.password.data):
                login_user(user_to_verify)
                flash(f'You are logging now! Welcome {user_to_verify.username}', category='success')
                return redirect(url_for('market_page'))
            else:
                flash('Username and password are not match! Please try again', category='danger')
            
        if form.errors != {}: #If there are not errors from the validations
            for err_msg in form.errors.values():
                flash(f'There was an error with creating a user: {err_msg}', category='danger')

        return render_template('login.html', form=form)

    flash(f"You are already logged in!", category='info')
    return redirect(url_for('market_page'))

@app.route("/mycart", methods=["GET", "POST"])
@login_required
def cart_page():
    remove_form = RemoveCartItemForm()
    user_cart = Cart.query.filter_by(userid=current_user.id).first()
    if request.method == "POST":
        if current_user.is_authenticated:
            removed_item = request.form.get('removed_item')
            r_item_object = Item.query.filter_by(name=removed_item).first()
            if r_item_object:
                user_cart.remove_item_from_cart(r_item_object)
                flash(f"The item '{r_item_object.name}' was removed successfully from your cart", category='success')
            else:
                flash(f"The item '{r_item_object.name}' has already been removed from your cart", category='danger')
        else:    
            flash(f"You need to create a account or login to the page for saved any item in a cart", category='danger')
            return redirect(url_for('market_page'))

    if request.method == "GET":        
        pass
        #TODO: Verificar porque siempre la pagina esta en modo post
    return render_template('mycart.html', user_cart=user_cart, remove_form=remove_form)


@app.route("/profile/<int:user_id>")
@login_required
def profile_page(user_id):
    user = User.query.filter_by(id=user_id).first()
    return render_template('profile.html', user=user)

@app.route("/logout")
@login_required
def logout_page():
    logout_user()
    flash(f"You've been logged out now ", category='info')
    return redirect(url_for('home_page'))

@app.route("/upload", methods=['GET', 'POST'])
@login_required
def upload_page():
    upload_form = SellItemForm()
    if upload_form.validate_on_submit():
        form_picture = upload_form.image.data
        item_to_create = Item(name=upload_form.name.data,
            price=upload_form.price.data,
            description=upload_form.description.data,
            creator=current_user.id,
            path_format=save_picture(form_picture),
            )
        db.session.add(item_to_create)
        db.session.commit()
        flash(f'Created', category='success')
        return redirect(url_for('market_page'))
    if upload_form.errors != {}: #If there are not errors from the validations
        for err_msg in upload_form.errors.items():
            flash(f'There was an error with uploading your item: {err_msg}', category='danger')
    return render_template('upload_page.html', upload_form=upload_form)

@app.route("/myitems")
@login_required
def my_items():
    my_items = Item.query.filter_by(owner=current_user.id)
    return render_template('my_items.html', my_items=my_items)


@app.errorhandler(404)
def not_found(e):
  return render_template("404.html"), 404


def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/uploads', picture_fn)

    output_size = (800, 800)
    im = Image.open(form_picture)
    if im.mode in ("RGBA", "P"):
        im = im.convert("RGB")
    im.thumbnail(output_size)
    im.save(picture_path)

    return picture_path
