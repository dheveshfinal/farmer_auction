from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from enum import Enum

db = SQLAlchemy()

class UserType(str, Enum):
    farmer = 'farmer'
    customer = 'customer'

class UserStatus(str, Enum):
    active = 'active'
    inactive = 'inactive'
    syspended = 'suspended'

class ProductStatus(str, Enum):
    draft = 'draft'
    active = 'active'
    sold = 'sold'
    cancelled = 'cancelled'

class AuctionStatus(str, Enum):
    upcoming = 'upcoming'
    active = 'active'
    ended = 'ended'
    cancelled = 'cancelled'

class BidStatus(str, Enum):
    active = 'active'
    WON = 'won'
    lost = 'lost'
    cancelled = 'cancelled'

class PaymentStatus(str, Enum):
    pending = 'pending'
    completed = 'completed'
    failed = 'failed'
    refunded = 'refunded'

class Users(db.Model):
    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    user_type = db.Column(db.Enum(UserType), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(15))
    address = db.Column(db.Text)
    created_at = db.Column(db.TIMESTAMP, default=datetime.utcnow)
    last_login = db.Column(db.TIMESTAMP)
    status = db.Column(db.Enum(UserStatus), default=UserStatus.active)

    # Relationships
    farmer_profile = db.relationship('FarmerProfiles', backref='user', uselist=False)
    products = db.relationship('Products', backref='farmer', foreign_keys='Products.farmer_id')
    bids = db.relationship('Bids', backref='bidder', foreign_keys='Bids.bidder_id')
    sales = db.relationship('Transactions', backref='seller', foreign_keys='Transactions.seller_id')
    purchases = db.relationship('Transactions', backref='buyer', foreign_keys='Transactions.buyer_id')

class FarmerProfiles(db.Model):
    farmer_id = db.Column(db.Integer, db.ForeignKey('users.user_id', ondelete='CASCADE'), primary_key=True)
    farm_name = db.Column(db.String(100))
    farm_location = db.Column(db.Text)
    farming_type = db.Column(db.String(100))
    years_of_experience = db.Column(db.Integer)
    certification_details = db.Column(db.Text)
    rating = db.Column(db.DECIMAL(3, 2))

class Categories(db.Model):
    category_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    parent_category_id = db.Column(db.Integer, db.ForeignKey('categories.category_id'))
    
    # Relationships
    subcategories = db.relationship('Categories', backref=db.backref('parent', remote_side=[category_id]))
    products = db.relationship('Products', backref='category')

class Products(db.Model):
    product_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    category_id = db.Column(db.Integer, db.ForeignKey('categories.category_id'))
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    quantity = db.Column(db.DECIMAL(10, 2), nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    base_price = db.Column(db.DECIMAL(10, 2), nullable=False)
    image_url = db.Column(db.Text)
    harvest_date = db.Column(db.Date)
    quality_grade = db.Column(db.String(20))
    status = db.Column(db.Enum(ProductStatus), default=ProductStatus.draft)
    created_at = db.Column(db.TIMESTAMP, default=datetime.utcnow)
    # Relationships
    auctions = db.relationship('Auctions', backref='product')

class Auctions(db.Model):
    auction_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.product_id'))
    start_time = db.Column(db.TIMESTAMP, nullable=False)
    end_time = db.Column(db.TIMESTAMP, nullable=False)
    min_bid_price = db.Column(db.DECIMAL(10, 2), nullable=False)
    current_highest_bid = db.Column(db.DECIMAL(10, 2))
    current_winner_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    status = db.Column(db.Enum(AuctionStatus), default=AuctionStatus.upcoming)
    # Relationships
    bids = db.relationship('Bids', backref='auction')
    current_winner = db.relationship('Users', foreign_keys=[current_winner_id])
    transaction = db.relationship('Transactions', backref='auction', uselist=False)

class Bids(db.Model):
    bid_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    auction_id = db.Column(db.Integer, db.ForeignKey('auctions.auction_id'))
    bidder_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    bid_amount = db.Column(db.DECIMAL(10, 2), nullable=False)
    bid_time = db.Column(db.TIMESTAMP, default=datetime.utcnow)
    status = db.Column(db.Enum(BidStatus), default=BidStatus.active)

class Transactions(db.Model):
    transaction_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    auction_id = db.Column(db.Integer, db.ForeignKey('auctions.auction_id'))
    seller_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    buyer_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    final_amount = db.Column(db.DECIMAL(10, 2), nullable=False)
    payment_status = db.Column(db.Enum(PaymentStatus), default=PaymentStatus.pending)
    payment_method = db.Column(db.String(50))
    transaction_date = db.Column(db.TIMESTAMP, default=datetime.utcnow)

    # Relationships
    reviews = db.relationship('Reviews', backref='transaction')

class Reviews(db.Model):
    review_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.transaction_id'))
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    reviewed_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    rating = db.Column(db.Integer)
    review_text = db.Column(db.Text)
    review_date = db.Column(db.TIMESTAMP, default=datetime.utcnow)

    # Relationships
    reviewer = db.relationship('Users', foreign_keys=[reviewer_id], backref='reviews_given')
    reviewed = db.relationship('Users', foreign_keys=[reviewed_id], backref='reviews_received')

    @db.validates('rating')
    def validate_rating(self, key, rating):
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")
        return rating