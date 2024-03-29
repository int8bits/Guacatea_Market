from flask import flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from market import app, db
from market.forms.auth_form import LoginForm, RegisterForm
from market.forms.cart_form import AddCartItemForm, RemoveCartItemForm
from market.forms.market_form import (BuyAllItemsForm, DeleteItemForm,
                                      PurchaseItemForm, SellItemForm)
from market.models.item import Item
from market.models.user import User

from .firebase_connection import upload_file


# /****************/
# /* Index page. */
# /****************/
@app.route('/')
@app.route('/home')
def home_page():
    return render_template('home.html')


# /****************/
# /* Auth routes. */
# /****************/
@app.route('/register', methods=["GET", "POST"])
def register_page():
    form = RegisterForm()
    if not current_user.is_authenticated:
        if form.validate_on_submit():
            user_to_create = User(username=form.username.data,
                                email=form.email.data,
                                password=form.password_1.data
                                )
            db.session.add(user_to_create)
            db.session.commit()
            login_user(user_to_create)
            flash(f'Account created successfully! You are now logged in as {user_to_create.username}', category='success')
            # Cuando se crea un Usuario se crea un Carrito que tiene el id del Usuario esto lo hace único
            session[user_to_create.username] = { 'cart': [] }
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
                session[form.username.data] = { 'cart': [] } if session.get(form.username.data) is None else session.get(form.username.data)

                return redirect(url_for('market_page'))
            else:
                flash('Username and password are not match! Please try again', category='danger')

        if form.errors != {}: #If there are not errors from the validations
            for err_msg in form.errors.values():
                flash(f'There was an error with creating a user: {err_msg}', category='danger')

        return render_template('login.html', form=form)

    flash(f"You are already logged in!", category='info')
    return redirect(url_for('market_page'))


@app.route("/logout")
@login_required
def logout_page():
    my_user = current_user.username
    session.pop(my_user, None)
    logout_user()
    flash(f"You've been logged out now ", category='info')
    return redirect(url_for('home_page'))


@app.route("/profile/<int:user_id>")
@login_required
def profile_page(user_id):
    user = User.query.filter_by(id=user_id).first()
    return render_template('profile.html', user=user)


# /***********************************/
# /* Market routes(items). */
# /***********************************/
@app.route('/market', methods=["GET", "POST"])
def market_page():
    purchase_form = PurchaseItemForm()
    cart_form = AddCartItemForm()
    delete_form = DeleteItemForm()
    cart_items = []

    if not current_user.is_anonymous:
        user_id = current_user.id
        my_user = current_user.username
        shopping_cart = session[my_user].get('cart')
        cart_items = db.session.query(Item).filter(Item.id.in_(shopping_cart)).all()

    if request.method == "POST":
        if current_user.is_authenticated:
            # Proceso de compra
            purchased_item_id = request.form.get('purchased_item')
            p_item_object = Item.query.filter_by(id=purchased_item_id).first()
            if p_item_object:
                if current_user.can_buy(p_item_object):
                    current_user.buy(p_item_object)
                    flash(f"Congratulations! You purchased the '{p_item_object.name}' for {p_item_object.price}$", category='success')
                else:
                    flash(f"Unfortunately, you don't have enough money to purchase the '{p_item_object.name}'", category='danger')
            # Proceso de agregar al carrito
            added_item_id = request.form.get('added_item')
            a_item_object = Item.query.filter_by(id=added_item_id).first()
            if a_item_object:
                try:
                    shopping_cart.append(a_item_object.id)
                    flash(f'You added the item: {a_item_object.name} to your cart successfully', category='success')
                except Exception as e:
                    flash(f"You already have the item in your cart.", category='info')
            # Proceso de eliminar articulos propios de la tienda
            del_item_id = request.form.get('deleted_item')
            d_item_object = Item.query.filter_by(id=del_item_id).first()
            if d_item_object:
                try:
                    db.session.delete(d_item_object)
                    db.session.commit()
                    flash(f"You delete {d_item_object.name} successfully!", category='success')
                except Exception as e:
                    flash(f"We have issues with deleting...", category='warning')

            return redirect(url_for('market_page'))
        else:
            flash(f"You need to create a account or login to the page for buy any item", category='danger')
            return redirect(url_for('market_page'))

    if request.method == "GET":
        items = Item.query.filter_by(owner=None)
        return render_template("market.html",items=items,
        purchase_form=purchase_form, cart_form=cart_form,
        cart_items=[item for item in cart_items],
        user_id=None if current_user.is_anonymous else current_user.id,
        delete_form=delete_form)


@app.route("/mycart", methods=["GET", "POST"])
@login_required
def cart_page():
    # FORMS
    purchase_form = PurchaseItemForm()
    buy_items_form = BuyAllItemsForm()
    remove_form = RemoveCartItemForm()

    my_user = current_user.username
    shopping_cart = session[my_user].get('cart', [])
    cart_items = db.session.query(Item).filter(Item.id.in_(shopping_cart)).all()
    get_total_price = sum(item.price for item in cart_items)
    session.modified = True

    if request.method == "POST":
        if current_user.is_authenticated:
            # Remover Artículos del carrito
            removed_item = request.form.get('removed_item')
            r_item_object = Item.query.filter_by(id=removed_item).first()
            if r_item_object:
                try:
                    shopping_cart.remove(r_item_object.id)

                except ValueError:
                    flash(f"The item has already been removed from the cart", category='info')
                flash(f"The item '{r_item_object.name}' was removed successfully from your cart", category='success')

            # Proceso de compra de UN artículo
            purchased_item = request.form.get('purchased_item')
            p_item_object = Item.query.filter_by(id=purchased_item).first()
            if p_item_object:
                if current_user.can_buy(p_item_object):
                    current_user.buy(p_item_object)
                    try:
                        shopping_cart.remove(p_item_object.id)
                    except ValueError:
                        flash(f"The item was removed successfully", category='info')
                    flash(f"Congratulations! You purchased the '{p_item_object.name}' for {p_item_object.price}$", category='success')
                else:
                    flash(f"Unfortunately, you don't have enough money to purchase the '{p_item_object.name}'", category='danger')

            #Proceso de compra de TODOS los artículos del carrito
            buy_confirmation = request.form.get('buy_confirmation')
            if buy_confirmation:
                if current_user.can_buy_all(get_total_price):
                    for item in cart_items:
                        p_item_object = Item.query.filter_by(id=item.id).first()
                        current_user.buy(p_item_object)
                        try:
                            shopping_cart.remove(p_item_object.id)
                        except ValueError:
                            flash(f"The item was removed successfully", category='info')

                    flash(f"Congratulations! You purchased the entire cart for {get_total_price}$", category='success')
                else:
                    flash(f"Unfortunately, you don't have enough money to purchase the entire cart", category='danger')
            return redirect(url_for('cart_page'))
        else:
            flash(f"You need to create a account or login to the page for saved any item in a cart", category='danger')
            return redirect(url_for('market_page'))
    if request.method == "GET":

        return render_template('mycart.html', remove_form=remove_form,
                            purchase_form=purchase_form, buy_items_form=buy_items_form,
                            get_total_price=get_total_price, cart_items=[item for item in cart_items])


@app.route("/myitems")
@login_required
def items_page():
    my_items = Item.query.filter_by(owner=current_user.id)
    return render_template('items_page.html', my_items=my_items)


# /****************/
# /* Other routes. */
# /****************/
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
            image=upload_file(form_picture),
            )
        db.session.add(item_to_create)
        db.session.commit()
        flash(f"You published your item '{item_to_create.name}' successfully", category='success')
        return redirect(url_for('market_page'))

    if upload_form.errors != {}: #If there are not errors from the validations
        for err_msg in upload_form.errors.items():
            flash(f'There was an error uploading your item: {err_msg}', category='danger')

    return render_template('upload_page.html', upload_form=upload_form)


@app.route("/terms")
def terms():
    return render_template('terms&conditions.html')


@app.route("/contact")
def contact():
    return render_template('contact_us.html')


@app.errorhandler(404)
def not_found(e):
  return render_template("404.html"), 404
