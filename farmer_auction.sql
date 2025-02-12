-- Users table to store both farmers and customers
CREATE TABLE users (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    user_type ENUM('farmer', 'customer') NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    phone_number VARCHAR(15),
    address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    status ENUM('active', 'inactive', 'suspended') DEFAULT 'active'
);

-- Farmer profiles with additional farmer-specific information
CREATE TABLE farmer_profiles (
    farmer_id INT PRIMARY KEY,
    farm_name VARCHAR(100),
    farm_location TEXT,
    farming_type VARCHAR(100),
    years_of_experience INT,
    certification_details TEXT,
    rating DECIMAL(3,2),
    FOREIGN KEY (farmer_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Product categories
CREATE TABLE categories (
    category_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(50) NOT NULL,
    description TEXT,
    parent_category_id INT,
    FOREIGN KEY (parent_category_id) REFERENCES categories(category_id)
);

-- Products table for items to be auctioned
CREATE TABLE products (
    product_id INT PRIMARY KEY AUTO_INCREMENT,
    farmer_id INT,
    category_id INT,
    title VARCHAR(100) NOT NULL,
    description TEXT,
    quantity DECIMAL(10,2) NOT NULL,
    unit VARCHAR(20) NOT NULL,
    base_price DECIMAL(10,2) NOT NULL,
    image_url TEXT,
    harvest_date DATE,
    quality_grade VARCHAR(20),
    status ENUM('draft', 'active', 'sold', 'cancelled') DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (farmer_id) REFERENCES users(user_id),
    FOREIGN KEY (category_id) REFERENCES categories(category_id)
);

-- Auctions table
CREATE TABLE auctions (
    auction_id INT PRIMARY KEY AUTO_INCREMENT,
    product_id INT,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    min_bid_price DECIMAL(10,2) NOT NULL,
    current_highest_bid DECIMAL(10,2),
    current_winner_id INT,
    status ENUM('upcoming', 'active', 'ended', 'cancelled') DEFAULT 'upcoming',
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (current_winner_id) REFERENCES users(user_id)
);

-- Bids table
CREATE TABLE bids (
    bid_id INT PRIMARY KEY AUTO_INCREMENT,
    auction_id INT,
    bidder_id INT,
    bid_amount DECIMAL(10,2) NOT NULL,
    bid_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status ENUM('active', 'won', 'lost', 'cancelled') DEFAULT 'active',
    FOREIGN KEY (auction_id) REFERENCES auctions(auction_id),
    FOREIGN KEY (bidder_id) REFERENCES users(user_id)
);

-- Transactions table for completed auctions
CREATE TABLE transactions (
    transaction_id INT PRIMARY KEY AUTO_INCREMENT,
    auction_id INT,
    seller_id INT,
    buyer_id INT,
    final_amount DECIMAL(10,2) NOT NULL,
    payment_status ENUM('pending', 'completed', 'failed', 'refunded') DEFAULT 'pending',
    payment_method VARCHAR(50),
    transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (auction_id) REFERENCES auctions(auction_id),
    FOREIGN KEY (seller_id) REFERENCES users(user_id),
    FOREIGN KEY (buyer_id) REFERENCES users(user_id)
);

-- Reviews and ratings
CREATE TABLE reviews (
    review_id INT PRIMARY KEY AUTO_INCREMENT,
    transaction_id INT,
    reviewer_id INT,
    reviewed_id INT,
    rating INT CHECK (rating >= 1 AND rating <= 5),
    review_text TEXT,
    review_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id),
    FOREIGN KEY (reviewer_id) REFERENCES users(user_id),
    FOREIGN KEY (reviewed_id) REFERENCES users(user_id)
);

DELIMITER //


-- Trigger to update current highest bid in auctions table
CREATE TRIGGER after_bid_insert
AFTER INSERT ON bids
FOR EACH ROW
BEGIN
    UPDATE auctions 
    SET current_highest_bid = NEW.bid_amount,
        current_winner_id = NEW.bidder_id
    WHERE auction_id = NEW.auction_id
    AND (current_highest_bid IS NULL OR NEW.bid_amount > current_highest_bid);
END//

-- Trigger to automatically start upcoming auctions
CREATE EVENT start_upcoming_auctions
ON SCHEDULE EVERY 1 MINUTE
DO
BEGIN
    UPDATE auctions
    SET status = 'active'
    WHERE start_time <= NOW()
    AND status = 'upcoming';
END//

-- Trigger to automatically end auction when end_time is reached
CREATE EVENT check_auction_status
ON SCHEDULE EVERY 1 MINUTE
DO
BEGIN
    UPDATE auctions 
    SET status = 'ended'
    WHERE end_time <= NOW() 
    AND status = 'active';
    
    -- Create transactions for ended auctions
    INSERT INTO transactions (auction_id, seller_id, buyer_id, final_amount)
    SELECT 
        a.auction_id,
        p.farmer_id,
        a.current_winner_id,
        a.current_highest_bid
    FROM auctions a
    JOIN products p ON a.product_id = p.product_id
    WHERE a.status = 'ended'
    AND a.auction_id NOT IN (SELECT auction_id FROM transactions)
    AND a.current_winner_id IS NOT NULL;
END//

-- Function to check if bid is valid
CREATE FUNCTION is_valid_bid(
    p_auction_id INT,
    p_bid_amount DECIMAL(10,2),
    p_bidder_id INT
) 
RETURNS BOOLEAN
DETERMINISTIC
READS SQL DATA
BEGIN
    DECLARE v_current_highest_bid DECIMAL(10,2);
    DECLARE v_min_bid_price DECIMAL(10,2);
    DECLARE v_auction_status VARCHAR(20);
    DECLARE v_farmer_id INT;
    
    SELECT 
        a.current_highest_bid,
        a.min_bid_price,
        a.status,  -- specify 'a.status' instead of just 'status' to avoid ambiguity
        p.farmer_id
    INTO 
        v_current_highest_bid,
        v_min_bid_price,
        v_auction_status,
        v_farmer_id
    FROM auctions a
    JOIN products p ON a.product_id = p.product_id
    WHERE a.auction_id = p_auction_id;
    
    -- Check if auction is active
    IF v_auction_status != 'active' THEN
        RETURN FALSE;
    END IF;
    
    -- Check if bidder is not the farmer
    IF v_farmer_id = p_bidder_id THEN
        RETURN FALSE;
    END IF;
    
    -- Check if bid is higher than minimum bid price
    IF p_bid_amount < v_min_bid_price THEN
        RETURN FALSE;
    END IF;
    
    -- Check if bid is higher than current highest bid
    IF v_current_highest_bid IS NOT NULL AND p_bid_amount <= v_current_highest_bid THEN
        RETURN FALSE;
    END IF;
    
    RETURN TRUE;
END//

-- Procedure to place a bid
CREATE PROCEDURE place_bid(
    IN p_auction_id INT,
    IN p_bidder_id INT,
    IN p_bid_amount DECIMAL(10,2),
    OUT p_success BOOLEAN,
    OUT p_message VARCHAR(100)
)
BEGIN
    DECLARE v_is_valid BOOLEAN;
    
    -- Check if bid is valid
    SET v_is_valid = is_valid_bid(p_auction_id, p_bid_amount, p_bidder_id);
    
    IF v_is_valid THEN
        INSERT INTO bids (auction_id, bidder_id, bid_amount)
        VALUES (p_auction_id, p_bidder_id, p_bid_amount);
        
        SET p_success = TRUE;
        SET p_message = 'Bid placed successfully';
    ELSE
        SET p_success = FALSE;
        SET p_message = 'Invalid bid';
    END IF;
END//

CREATE PROCEDURE get_all_active_auctions()
BEGIN
    SELECT a.auction_id, a.product_id, a.start_time, a.end_time, a.min_bid_price, 
           a.current_highest_bid, a.current_winner_id, a.status,
           p.title AS product_title, p.description AS product_description, 
           u.username AS farmer_name
    FROM auctions a
    JOIN products p ON a.product_id = p.product_id
    JOIN users u ON p.farmer_id = u.user_id
    WHERE a.status = 'active';
END//

-- Procedure to start an auction
CREATE PROCEDURE start_auction(
    IN p_product_id INT,
    IN p_start_time TIMESTAMP,
    IN p_end_time TIMESTAMP,
    IN p_min_bid_price DECIMAL(10,2),
    OUT p_success BOOLEAN,
    OUT p_message VARCHAR(100)
)
BEGIN
    DECLARE v_product_status VARCHAR(20);
    
    -- Check product status
    SELECT status INTO v_product_status
    FROM products
    WHERE product_id = p_product_id;
    
    IF v_product_status = 'active' THEN
        INSERT INTO auctions (
            product_id,
            start_time,
            end_time,
            min_bid_price,
            status
        )
        VALUES (
            p_product_id,
            p_start_time,
            p_end_time,
            p_min_bid_price,
            CASE 
                WHEN p_start_time <= NOW() THEN 'active'
                ELSE 'upcoming'
            END
        );
        
        UPDATE products
        SET status = 'active'
        WHERE product_id = p_product_id;
        
        SET p_success = TRUE;
        SET p_message = 'Auction created successfully';
    ELSE
        SET p_success = FALSE;
        SET p_message = 'Product is not available for auction';
    END IF;
END//

CREATE PROCEDURE cancel_auction(IN auction_id INT, IN user_id INT)
BEGIN
    DECLARE auction_owner INT;
    
    -- Check if the auction exists and get the owner
    SELECT p.farmer_id INTO auction_owner
    FROM auctions a
    JOIN products p ON a.product_id = p.product_id
    WHERE a.auction_id = auction_id;

    -- Ensure the auction belongs to the calling farmer and is in an active or upcoming state
    IF auction_owner = user_id THEN
        UPDATE auctions
        SET status = 'cancelled'
        WHERE auction_id = auction_id AND status IN ('active', 'upcoming');
        
        UPDATE bids
        SET status = 'cancelled'
        WHERE auction_id = auction_id;
        
    ELSE
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Unauthorized or invalid auction status for cancellation.';
    END IF;
END//

CREATE PROCEDURE GetUserAuctions(IN input_user_id INT)
BEGIN
    SELECT 
        a.auction_id,
        a.product_id,
        p.title AS product_title,
        p.description AS product_description,
        a.start_time,
        a.end_time,
        a.min_bid_price,
        a.current_highest_bid,
        a.status AS auction_status,
        b.bid_id,
        b.bid_amount,
        b.bid_time,
        b.status AS bid_status
    FROM 
        auctions AS a
    INNER JOIN 
        bids AS b ON a.auction_id = b.auction_id
    INNER JOIN 
        products AS p ON a.product_id = p.product_id
    WHERE 
        b.bidder_id = input_user_id
    ORDER BY 
        a.end_time DESC;
END //

DELIMITER ;

