from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
# from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
from functools import wraps
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from enum import Enum
from sqlalchemy import text
from models import *

app = Flask(__name__)
app.secret_key = 'farmer_auction'  # Change this to a secure secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:mysql@localhost:3306/farmer_auction'  # Update with your MySQL credentials
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Login decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes for Authentication
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = db.session.execute(db.select(Users).filter_by(email=email)).scalar_one_or_none()
        
        if user and user.password_hash==password:
            session['user_id'] = user.user_id
            session['user_type'] = user.user_type
            session['username'] = user.username
            flash('Logged in successfully!')
            return redirect(url_for('dashboard'))
            
        flash('Invalid credentials.')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user_data = {
            'username': request.form['username'],
            'email': request.form['email'],
            'password_hash': request.form['password'],
            'user_type': request.form['user_type'],
            'full_name': request.form['full_name'],
            'phone_number': request.form['phone_number'],
            'address': request.form['address']
        }
        
        new_user = Users(**user_data)
        db.session.add(new_user)
        db.session.commit()
        
        if user_data['user_type'] == 'farmer':
            farmer_profile = FarmerProfiles(
                farmer_id=new_user.user_id,
                farm_name=request.form['farm_name'],
                farm_location=request.form['farm_location'],
                farming_type=request.form['farming_type'],
                years_of_experience=request.form['years_of_experience'],
                certification_details=request.form['certification_details']
            )
            db.session.add(farmer_profile)
            
        db.session.commit()
        flash('Registration successful!')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!')
    return redirect(url_for('login'))

# Routes for Farmers
@app.route('/farmer/products', methods=['GET'])
@login_required
def farmer_products():
    if session['user_type'] != 'farmer':
        flash('Access denied.')
        return redirect(url_for('dashboard'))
        
    products = db.session.execute(
        db.select(Products).filter_by(farmer_id=session['user_id'])
    ).scalars().all()
    return render_template('farmer/product.html', products=products,user_status=ProductStatus)

@app.route('/farmer/new_product', methods=['GET', 'POST'])
@login_required
def new_product():
    if request.method == 'POST':
        product_data = {
            'farmer_id': session['user_id'],
            'category_id': request.form['category_id'],
            'title': request.form['title'],
            'description': request.form['description'],
            'quantity': request.form['quantity'],
            'unit': request.form['unit'],
            'base_price': request.form['base_price'],
            'harvest_date': request.form['harvest_date'],
            'quality_grade': request.form['quality_grade']
        }
        
        new_product = Products(**product_data)
        db.session.add(new_product)
        db.session.commit()
        flash('Product added successfully!')
        return redirect(url_for('farmer_products'))
        
    categories = db.session.execute(db.select(Categories)).scalars().all()
    return render_template('farmer/new_product.html', categories=categories)

@app.route('/farmer/my_auctions', methods=['GET'])
@login_required
def farmer_auctions():
    if session.get('user_type') != 'farmer':
        flash('Access denied.')
        return redirect(url_for('dashboard'))
    
    # Retrieve auctions filtered by status for the logged-in farmer
    auctions = {
        'upcoming': db.session.execute(
            db.select(Auctions).join(Products).filter(
                Auctions.status == AuctionStatus.upcoming,
                Products.farmer_id == session['user_id']
            )
        ).scalars().all(),
        'active': db.session.execute(
            db.select(Auctions).join(Products).filter(
                Auctions.status == AuctionStatus.active,
                Products.farmer_id == session['user_id']
            )
        ).scalars().all(),
        'ended': db.session.execute(
            db.select(Auctions).join(Products).filter(
                Auctions.status == AuctionStatus.ended,
                Products.farmer_id == session['user_id']
            )
        ).scalars().all(),
        'cancelled': db.session.execute(
            db.select(Auctions).join(Products).filter(
                Auctions.status == AuctionStatus.cancelled,
                Products.farmer_id == session['user_id']
            )
        ).scalars().all()
    }
    return render_template('farmer/my_auctions.html', auctions=auctions)

# Routes for Customers
@app.route('/auctions', methods=['GET'])
@login_required
def browse_auctions():
    try:
        # Call the stored procedure
        result = db.session.execute(text('CALL get_all_active_auctions()'))
        
        # Fetch all results from the procedure call
        active_auctions = result.fetchall()
        
        # Convert results to a list of dictionaries for easier use in the template
        auctions = [
            {
                'auction_id': row[0],
                'product_id': row[1],
                'start_time': row[2],
                'end_time': row[3],
                'min_bid_price': row[4],
                'current_highest_bid': row[5],
                'current_winner_id': row[6],
                'status': row[7],
                'product_title': row[8],
                'product_description': row[9],
                'farmer_name': row[10]
            }
            for row in active_auctions
        ]

    except Exception as e:
        flash(f'Error fetching active auctions: {str(e)}')
        auctions = []
    
    return render_template('auctions.html', auctions=auctions)


@app.route('/auction/<int:auction_id>', methods=['GET'])
def auction_detail(auction_id):
    auction = db.session.get(Auctions, auction_id)
    bids = db.session.execute(
        db.select(Bids).filter_by(auction_id=auction_id).order_by(Bids.bid_amount.desc())
    ).scalars().all()
    return render_template('auction_detail.html', auction=auction, bids=bids)

@app.route('/place_bid', methods=['POST'])
@login_required
def place_bid():
    auction_id = request.form['auction_id']
    bid_amount = request.form['bid_amount']
    
    success = False
    message = ''
    
    # Call the stored procedure
    result = db.session.execute(
        text('CALL place_bid(:auction_id, :bidder_id, :bid_amount, @success, @message)'),
        {'auction_id': auction_id, 'bidder_id': session['user_id'], 'bid_amount': bid_amount}
    )
    db.session.commit()
    
    success_result = db.session.execute(text('SELECT @success AS success, @message AS message')).mappings().fetchone()
    success = success_result['success']
    message = success_result['message']
    
    if success:
        flash('Bid placed successfully!')
    else:
        flash(f'Error placing bid: {message}')
        
    return redirect(url_for('auction_detail', auction_id=auction_id))

# Dashboard routes
@app.route('/dashboard')
@login_required
def dashboard():
    if session['user_type'] == 'farmer':
        products = db.session.execute(
            db.select(Products).filter_by(farmer_id=session['user_id'])
        ).scalars().all()

        auctions = db.session.execute(
            db.select(Auctions).join(Products).filter(Products.farmer_id == session['user_id'])
        ).scalars().all()

        bids = db.session.execute(
            db.select(Bids)
            .join(Auctions)
            .join(Products)
            .filter(Products.farmer_id == session['user_id'])
            .order_by(Bids.bid_time.desc())
        ).scalars().all()
        return render_template('farmer/dashboard.html', products=products, auctions=auctions, bids=bids)
    else:
        participating_auctions = db.session.execute(
            db.select(Auctions, Products, Bids)
            .join(Bids, Auctions.auction_id == Bids.auction_id)
            .join(Products, Auctions.product_id == Products.product_id)
            .filter(Bids.bidder_id == session['user_id'], Auctions.status == 'active')
            .order_by(Auctions.end_time.desc())
        ).all()

        # Fetch won auctions for the user
        won_auctions = db.session.execute(
            db.select(Auctions, Products)
            .join(Products, Auctions.product_id == Products.product_id)
            .filter(Auctions.current_winner_id == session['user_id'], Auctions.status == 'ended')
        ).all()

        participating_auctions_list = [
        {
            'auction_id': auction.auction_id,
            'product_title': product.title,
            'bid_amount': bid.bid_amount,
            'current_highest_bid': auction.current_highest_bid,
            'end_time': auction.end_time,
            'auction_status': auction.status
        }
        for auction, product, bid in participating_auctions
        ]

        won_auctions_list = [
        {
            'auction_id': auction.auction_id,
            'product_title': product.title,
            'winning_bid': auction.current_highest_bid,
            'auction_status': auction.status,
            'transaction_id': db.session.execute(
                db.select(Transactions.transaction_id)
                .filter_by(auction_id=auction.auction_id, buyer_id=session['user_id'])
            ).scalar_one_or_none()
        }
        for auction, product in won_auctions
        ]
        return render_template('customer/dashboard.html',participating_auctions=participating_auctions_list, 
                           won_auctions=won_auctions_list)

@app.route('/cancel_auction', methods=['POST'])
@login_required
def cancel_auction():
    if session.get('user_type') != 'farmer':
        flash('Access denied.')
        return redirect(url_for('dashboard'))
    
    auction_id = request.form.get('auction_id')
    
    try:
        # Call the stored procedure with auction_id and session['user_id']
        db.session.execute(
            text('CALL cancel_auction(:auction_id, :user_id)'),
            {'auction_id': auction_id, 'user_id': session['user_id']}
        )
        db.session.commit()
        flash('Auction cancelled successfully!')
    except Exception as e:
        db.session.rollback()
        flash(f'Failed to cancel the auction: {str(e)}')

    return redirect(url_for('farmer_auctions'))



# API endpoints for AJAX calls
@app.route('/api/check_bid', methods=['POST'])
@login_required
def check_bid():
    data = request.get_json()
    result = db.session.execute(
        'SELECT is_valid_bid(:auction_id, :bid_amount, :bidder_id) as valid',
        {
            'auction_id': data['auction_id'],
            'bid_amount': data['bid_amount'],
            'bidder_id': session['user_id']
        }
    ).scalar()
    return jsonify({'valid': bool(result)})

# Route to display the new auction form
@app.route('/farmer/new_auction')
def new_auction():
    if session.get('user_type') != 'farmer':
        flash('Access denied.')
        return redirect(url_for('dashboard'))
    # Fetch the products for the dropdown (only 'active' status products not in an auction)
    farmer_id = session.get('user_id')
    products = db.session.execute(text("SELECT product_id, title FROM products WHERE status = 'active' AND farmer_id = :farmer_id"),{'farmer_id':farmer_id}).fetchall()
    return render_template('farmer/new_auction.html', products=products)

# Route to handle auction creation
@app.route('/create_auction', methods=['POST'])
def create_auction():
    product_id = request.form.get('product_id')
    start_time = request.form.get('start_time')
    end_time = request.form.get('end_time')
    min_bid_price = request.form.get('min_bid_price')

    # Execute the stored procedure to start the auction
    try:
        result = db.session.execute(
            text("CALL start_auction(:p_product_id, :p_start_time, :p_end_time, :p_min_bid_price, @p_success, @p_message)"),
            {'p_product_id': product_id, 'p_start_time': start_time, 'p_end_time': end_time, 'p_min_bid_price': min_bid_price}
        )
        db.session.commit()
        # Fetch the output parameters
        success = db.session.execute(text("SELECT @p_success AS success, @p_message AS message")).mappings().fetchone()
        
        if success['success']:
            flash(success['message'], 'success')
        else:
            flash(success['message'], 'error')
    except Exception as e:
        flash(f"An error occurred: {str(e)}", 'error')

    return redirect(url_for('farmer_auctions'))

@app.route('/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    product = db.session.get(Products,product_id)
    try:
        db.session.delete(product)
        db.session.commit()
        flash("Product deleted successfully", "success")
    except:
        db.session.rollback()
        flash("Error deleting product", "error")
    return redirect(url_for('farmer_products'))

@app.route('/transaction/<int:transaction_id>', methods=['GET'])
def view_transaction(transaction_id):
    # Check if the user is logged in
    if 'user_id' not in session:
        flash("Please log in to view your transaction.")
        return redirect(url_for('login'))

    # Fetch the transaction details
    transaction = db.session.execute(
        db.select(Transactions)
        .filter_by(transaction_id=transaction_id, buyer_id=session['user_id'])
    ).scalar_one_or_none()

    if transaction is None:
        flash("Transaction not found or unauthorized access.")
        return redirect(url_for('home'))

    # Render the transaction page
    return render_template('transaction.html', transaction=transaction)


@app.route('/transaction/confirm/<int:transaction_id>', methods=['POST'])
def confirm_transaction(transaction_id):
    # Check if the user is logged in
    if 'user_id' not in session:
        flash("Please log in to confirm the transaction.")
        return redirect(url_for('login'))

    # Fetch the transaction record
    transaction = db.session.execute(
        db.select(Transactions)
        .filter_by(transaction_id=transaction_id, buyer_id=session['user_id'], payment_status='pending')
    ).scalar_one_or_none()

    if transaction is None:
        flash("Transaction not found or already completed.")
        return redirect(url_for('home'))

    # Update the payment status to completed
    transaction.payment_status = 'completed'
    db.session.commit()

    flash("Transaction completed successfully!")
    return redirect(url_for('view_transaction', transaction_id=transaction_id))

@app.route('/update_product_status/<int:product_id>', methods=['POST'])
@login_required
def update_product_status(product_id):
    # Check if the user is a farmer
    if session.get('user_type') != 'farmer':
        flash('Access denied.')
        return redirect(url_for('dashboard'))

    farmer_id = session.get('user_id')
    if not farmer_id:
        flash("User ID not found in session.")
        return redirect(url_for('dashboard'))

    # Get the product and verify ownership
    product = product = db.session.get(Products,product_id)
    if product.farmer_id != farmer_id:
        flash("You are not authorized to update this product.")
        return redirect(url_for('farmer_products'))

    # Update the product status
    new_status = request.form.get('status')
    if new_status in ['draft', 'active', 'sold', 'cancelled']: 
        product.status = new_status
        db.session.commit()
        flash("Product status updated successfully", "success")
    else:
        flash("Invalid status value", "error")

    return redirect(url_for('farmer_products'))

if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True)
