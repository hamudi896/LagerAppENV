import pandas as pd
from io import BytesIO
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy

# Flask app initialisieren
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///warenwirtschaft.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Datenbankmodelle
class Shop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    stocks = db.relationship('Stock', backref='shop', lazy=True)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)

class Stock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    quantity = db.Column(db.Integer, default=0)

# Datenbank initialisieren
with app.app_context():
    db.create_all()

# Routen
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/shops', methods=['GET', 'POST'])
def shops():
    if request.method == 'POST':
        shop_name = request.form['name']
        new_shop = Shop(name=shop_name)
        db.session.add(new_shop)
        db.session.commit()
        return redirect(url_for('shops'))
    shops = Shop.query.all()
    return render_template('shops.html', shops=shops)

@app.route('/shops/<int:shop_id>', methods=['GET'])
def shop_details(shop_id):
    shop = Shop.query.get_or_404(shop_id)
    categories = Category.query.all()
    items = Item.query.all()

    # Bestandsliste vorbereiten
    stocks = {item.id: 0 for item in items}
    for stock in Stock.query.filter_by(shop_id=shop_id).all():
        stocks[stock.item_id] = stock.quantity

    # Artikel nach Kategorien gruppieren
    items_grouped = {}
    for category in categories:
        category_items = [
            {"item": item, "quantity": stocks[item.id]}
            for item in items if item.category_id == category.id
        ]
        items_grouped[category.name] = category_items

    return render_template('shop_details.html', shop=shop, items_grouped=items_grouped)

@app.route('/shops/adjust_stock', methods=['POST'])
def adjust_stock():
    data = request.get_json()
    shop_id = data.get('shop_id')
    item_id = data.get('item_id')
    adjustment = data.get('adjustment', 0)

    if not all([shop_id, item_id, adjustment]):
        return jsonify({'error': 'Ungültige Anfrageparameter'}), 400

    stock = Stock.query.filter_by(shop_id=shop_id, item_id=item_id).first()
    if not stock:
        stock = Stock(shop_id=shop_id, item_id=item_id, quantity=0)
        db.session.add(stock)

    stock.quantity += adjustment
    if stock.quantity < 0:
        stock.quantity = 0
    db.session.commit()

    return jsonify({'new_quantity': stock.quantity})

@app.route('/shops/add_stock', methods=['POST'])
def add_stock():
    data = request.get_json()
    shop_id = data.get('shop_id')
    item_id = data.get('item_id')
    adjustment = data.get('adjustment', 0)

    if not all([shop_id, item_id, adjustment]):
        return jsonify({'error': 'Ungültige Anfrageparameter'}), 400

    stock = Stock.query.filter_by(shop_id=shop_id, item_id=item_id).first()
    if not stock:
        stock = Stock(shop_id=shop_id, item_id=item_id, quantity=0)
        db.session.add(stock)

    stock.quantity += adjustment
    db.session.commit()

    return jsonify({'new_quantity': stock.quantity})

@app.route('/categories', methods=['GET', 'POST'])
def categories():
    if request.method == 'POST':
        category_name = request.form['name']
        new_category = Category(name=category_name)
        db.session.add(new_category)
        db.session.commit()
        return redirect(url_for('categories'))
    categories = Category.query.all()
    return render_template('categories.html', categories=categories)

@app.route('/categories/edit/<int:category_id>', methods=['GET', 'POST'])
def edit_category(category_id):
    category = Category.query.get_or_404(category_id)
    if request.method == 'POST':
        category.name = request.form['name']
        db.session.commit()
        return redirect(url_for('categories'))
    return render_template('edit_category.html', category=category)

@app.route('/categories/delete/<int:category_id>', methods=['POST'])
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    db.session.delete(category)
    db.session.commit()
    return redirect(url_for('categories'))

@app.route('/items', methods=['GET', 'POST'])
def items():
    if request.method == 'POST':
        item_name = request.form['name']
        category_id = request.form['category_id']
        new_item = Item(name=item_name, category_id=category_id)
        db.session.add(new_item)
        db.session.commit()
        return redirect(url_for('items'))
    categories = Category.query.all()
    items_grouped = {}
    for category in categories:
        items_grouped[category.name] = Item.query.filter_by(category_id=category.id).all()
    return render_template('items.html', items_grouped=items_grouped, categories=categories)

@app.route('/items/edit/<int:item_id>', methods=['GET', 'POST'])
def edit_item(item_id):
    item = Item.query.get_or_404(item_id)
    categories = Category.query.all()
    if request.method == 'POST':
        item.name = request.form['name']
        item.category_id = request.form['category_id']
        db.session.commit()
        return redirect(url_for('items'))
    return render_template('edit_item.html', item=item, categories=categories)

@app.route('/items/delete/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    item = Item.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('items'))

@app.route('/dashboard', methods=['GET'])
def dashboard():
    categories = Category.query.all()
    items = Item.query.all()
    shops = Shop.query.all()

    if not categories or not items or not shops:
        return render_template('dashboard.html', matrix={}, shops=[])

    matrix = {}
    for category in categories:
        matrix[category.name] = {}
        category_items = [item for item in items if item.category_id == category.id]
        for item in category_items:
            matrix[category.name][item.name] = {}
            for shop in shops:
                stock = Stock.query.filter_by(shop_id=shop.id, item_id=item.id).first()
                matrix[category.name][item.name][shop.name] = stock.quantity if stock else 0

    return render_template('dashboard.html', matrix=matrix, shops=shops)

@app.route('/export_dashboard', methods=['GET'])
def export_dashboard():
    categories = Category.query.all()
    items = Item.query.all()
    shops = Shop.query.all()

    # Bestandsdaten vorbereiten
    data = []
    for category in categories:
        category_items = [item for item in items if item.category_id == category.id]
        for item in category_items:
            row = {'Warengruppe': category.name, 'Artikel': item.name}
            for shop in shops:
                stock = Stock.query.filter_by(shop_id=shop.id, item_id=item.id).first()
                row[shop.name] = stock.quantity if stock else 0
            data.append(row)

    # Erstellen eines DataFrames aus den Daten
    df = pd.DataFrame(data)

    # Erstellen eines Excel-Exports im Speicher
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Bestände')

    output.seek(0)

    # Excel-Datei senden
    return send_file(output, as_attachment=True, download_name="dashboard_bestande.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)