import csv
import os
from datetime import date, timedelta
import random

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def generate_mock_data():
    csv_dir = os.path.join(project_root, "db", "csv_data")
    os.makedirs(csv_dir, exist_ok=True)

    # 1. Generate Customers (Indian Context)
    customers = [
        (1, 'Rahul Sharma', 'rahul.s@example.com', '9876543210'),
        (2, 'Priya Patel', 'priya.p@example.com', '9876543211'),
        (3, 'Amit Singh', 'amit.s@example.com', '9876543212'),
        (4, 'Anjali Gupta', 'anjali.g@example.com', '9876543213'),
        (5, 'Vikram Verma', 'vikram.v@example.com', '9876543214'),
        (6, 'Neha Reddy', 'neha.r@example.com', '9876543215'),
        (7, 'Suresh Iyer', 'suresh.i@example.com', '9876543216'),
        (8, 'Kavita Joshi', 'kavita.j@example.com', '9876543217'),
        (9, 'Rajesh Kumar', 'rajesh.k@example.com', '9876543218'),
        (10, 'Sneha Desai', 'sneha.d@example.com', '9876543219'),
        (11, 'Ravi Menon', 'ravi.m@example.com', '9876543220'),
        (12, 'Pooja Agarwal', 'pooja.a@example.com', '9876543221'),
        (13, 'Deepak Nair', 'deepak.n@example.com', '9876543222'),
        (14, 'Meera Chatterjee', 'meera.c@example.com', '9876543223'),
        (15, 'Arjun Kapoor', 'arjun.k@example.com', '9876543224')
    ]
    with open(os.path.join(csv_dir, 'customers.csv'), 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['customer_id', 'name', 'email', 'phone'])
        writer.writerows(customers)

    # 2. Generate Items
    items = []
    item_id = 1001
    categories = {
        'Groceries': [
            ('Aashirvaad Select Sharbati Atta 5kg', 350.00, 'Non-Returnable'), ('Tata Salt 1kg', 28.00, 'Non-Returnable'), 
            ('Amul Taaza Milk 1L', 70.00, 'Non-Returnable'), ('India Gate Basmati Rice 5kg', 850.00, '7 Days Return'),
            ('Haldiram Bhujia Sev 400g', 110.00, 'Non-Returnable'), ('Maggi 2-Minute Noodles 12-Pack', 168.00, 'Non-Returnable'),
            ('Brooke Bond Red Label Tea 500g', 270.00, 'Non-Returnable'), ('Fortune Sunlite Refined Sunflower Oil 1L', 145.00, 'Non-Returnable'),
            ('Everest Garam Masala 100g', 85.00, 'Non-Returnable'), ('Britannia Good Day Cookies 600g', 150.00, 'Non-Returnable'),
            ('Patanjali Cow Ghee 1L', 650.00, 'Non-Returnable'), ('Amul Butter 500g', 285.00, 'Non-Returnable'),
            ('Mother Dairy Paneer 200g', 85.00, 'Non-Returnable'), ('Saffola Gold Cooking Oil 5L', 950.00, 'Non-Returnable'),
            ('Dabur Honey 500g', 230.00, 'Non-Returnable'), ('Kissan Tomato Ketchup 1kg', 140.00, 'Non-Returnable'),
            ('Tata Sampann Toor Dal 1kg', 190.00, 'Non-Returnable'), ('Gowardhan Ghee 1L', 680.00, 'Non-Returnable'),
            ('MTR Rava Idli Mix 500g', 120.00, 'Non-Returnable'), ('Surf Excel Easy Wash 1kg', 135.00, 'Non-Returnable'),
            ('Vim Dishwash Liquid 500ml', 105.00, 'Non-Returnable'), ('Ariel Matic Front Load 1kg', 250.00, 'Non-Returnable'),
            ('Himalaya Purifying Neem Face Wash 150ml', 210.00, 'Non-Returnable'), ('Dettol Antiseptic Liquid 500ml', 195.00, 'Non-Returnable')
        ],
        'Clothing': [
            ('FabIndia Men Cotton Kurta', 1299.00, '15 Days Return'), ('Biba Women Printed Salwar Suit', 2499.00, '15 Days Return'),
            ('Raymond Premium Cotton Shirt', 1899.00, '15 Days Return'), ('Manyavar Wedding Sherwani', 15000.00, '7 Days Return'),
            ('W for Woman Straight Kurti', 1199.00, '15 Days Return'), ('Levis Men 511 Slim Fit Jeans', 2999.00, '30 Days Return'),
            ('Allen Solly Polo T-Shirt', 899.00, '15 Days Return'), ('Nalli Silk Saree', 8500.00, '7 Days Return'),
            ('Kanchipuram Art Silk Saree', 3500.00, '7 Days Return'), ('Peter England Formal Trousers', 1499.00, '15 Days Return'),
            ('Jockey Men Innerwear 3-Pack', 599.00, 'Non-Returnable'), ('Puma Men Running Shoes', 3499.00, '30 Days Return'),
            ('Bata Women Sandals', 899.00, '15 Days Return'), ('Red Tape Leather Loafers', 2199.00, '15 Days Return'),
            ('Aurelia Women Dupatta', 499.00, '15 Days Return'), ('H&M Basic White T-Shirt', 499.00, '30 Days Return'),
            ('Zara Men Winter Jacket', 4500.00, '30 Days Return'), ('Global Desi Maxi Dress', 2199.00, '15 Days Return'),
            ('Ruched Georgette Lehenga', 5500.00, '7 Days Return'), ('Titan Skinn Perfume 100ml', 1495.00, 'Non-Returnable'),
            ('Lakme Eyeconic Kajal', 250.00, 'Non-Returnable'), ('Nykaa Matte Lipstick', 399.00, 'Non-Returnable'),
            ('Bata Men Casual Shoes', 1799.00, '30 Days Return'), ('Pepe Jeans', 2999.00, '30 Days Return'),
            ('Womens Cotton Nightdress', 699.00, '15 Days Return'),('Mens Cotton Boxer Shorts 3-Pack', 799.00, 'Non-Returnable'),
        ],
        'Electronics': [
            ('boAt Airdopes 141', 1299.00, '7 Days Replacement'), ('Noise ColorFit Pro 4 Smartwatch', 2499.00, '7 Days Replacement'),
            ('Xiaomi Power Bank 3i 20000mAh', 2199.00, '7 Days Replacement'), ('OnePlus Nord Buds 2', 2999.00, '7 Days Replacement'),
            ('Portronics USB Hub 4-Port', 399.00, '15 Days Return'), ('Samsung Galaxy M14 5G', 13990.00, '7 Days Replacement'),
            ('Apple iPhone 15 128GB', 79900.00, '7 Days Replacement'), ('Sony WH-1000XM5 Headphones', 29990.00, '7 Days Replacement'),
            ('JBL Flip 6 Bluetooth Speaker', 11999.00, '7 Days Replacement'), ('SanDisk 128GB Pendrive', 899.00, '15 Days Return'),
            ('Logitech M235 Wireless Mouse', 799.00, '15 Days Return'), ('HP Wired Keyboard and Mouse', 1299.00, '15 Days Return'),
            ('Realme Buds Wireless 2 Neo', 1499.00, '7 Days Replacement'), ('Ambrane 10000mAh Powerbank', 999.00, '7 Days Replacement'),
            ('Boult Audio Z40 True Wireless', 1199.00, '7 Days Replacement'), ('Amazon Echo Dot (4th Gen)', 3499.00, '15 Days Return'),
            ('Fire TV Stick with Alexa', 3999.00, '15 Days Return'), ('Kindle Paperwhite 16GB', 13999.00, '15 Days Return'),
            ('Philips Trimmer QP2525', 1499.00, 'Non-Returnable'), ('Omron BP Monitor', 2150.00, 'Non-Returnable')
        ],
        'Home Appliances': [
            ('Prestige Svachh Pressure Cooker 3L', 1450.00, '15 Days Return'), ('Bajaj Rex Mixer Grinder 500W', 2299.00, '7 Days Replacement'),
            ('Havells Nicola Ceiling Fan', 2650.00, '7 Days Replacement'), ('Voltas 1.5 Ton Split AC', 32990.00, '7 Days Replacement'),
            ('Godrej 190L Single Door Refrigerator', 15490.00, '7 Days Replacement'), ('Pigeon Induction Cooktop', 1699.00, '15 Days Return'),
            ('LG 8 Kg Fully Automatic Washing Machine', 21990.00, '7 Days Replacement'), ('Samsung 28L Convection Microwave', 12490.00, '7 Days Replacement'),
            ('Philips Iron Box 1000W', 850.00, '15 Days Return'), ('Usha Room Heater 2000W', 1499.00, '7 Days Replacement'),
            ('Crompton Amica Water Heater 15L', 6599.00, '7 Days Replacement'), ('Eureka Forbes Aquaguard Water Purifier', 14999.00, '7 Days Replacement'),
            ('Kent Grand RO Water Purifier', 15500.00, '7 Days Replacement'), ('Milton Thermosteel Flask 1L', 950.00, '15 Days Return'),
            ('Cello Opalware Dinner Set 33pcs', 1899.00, '15 Days Return'), ('Dyson V11 Absolute Vacuum Cleaner', 52900.00, '15 Days Return'),
            ('IFB 20L Solo Microwave Oven', 6290.00, '7 Days Replacement'), ('Whirlpool 240L Frost Free Refrigerator', 24990.00, '7 Days Replacement'),
            ('Sony Bravia 55 inch 4K Ultra HD TV', 64990.00, '7 Days Replacement'), ('Mi Smart TV 43 inch 4K', 25999.00, '7 Days Replacement')
        ]
    }
    
    for category, products in categories.items():
        for name, price, return_policy in products:
            items.append((item_id, name, f"{category} product", category, price, return_policy))
            item_id += 1

    with open(os.path.join(csv_dir, 'items.csv'), 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['item_id', 'name', 'description', 'category', 'base_price', 'return_policy'])
        writer.writerows(items)

    # 3. Generate 200 Orders dynamically
    random.seed(42) # For reproducibility
    today = date.today()
    payment_methods = ['Credit Card', 'UPI', 'Store Credit', 'Debit Card', 'Net Banking']
    orders = []
    tickets = []
    ticket_id = 9001
    
    for order_id in range(10001, 10251):
        customer_id = random.randint(1, 15)
        item = random.choice(items)
        i_id = item[0]
        i_price = item[4]
        i_policy = item[5]
        
        quantity = random.choices([1, 2, 3, 4, 5], weights=[70, 15, 10, 3, 2])[0]
        total_amount = round(quantity * i_price, 2)
        
        days_ago = random.randint(1, 120)
        order_date = today - timedelta(days=days_ago)
        delivery_days = random.randint(1, 7)
        delivery_date = order_date + timedelta(days=delivery_days)
        
        payment = random.choice(payment_methods)
        
        # refund_status logic: mostly 'None'. Some 'Requested', 'Processed', 'Rejected'
        # We don't calculate eligibility here, just the explicit action the user/system took.
        refund_action = random.choices(['None', 'Requested', 'Processed', 'Rejected'], weights=[85, 5, 5, 5])[0]
        ticket_type = 'Replacement' if 'Replacement' in i_policy else 'Return'
        refund_status = f"{ticket_type} {refund_action}" if refund_action != 'None' else 'None'
        
        # Generate tickets based on hard status
        if refund_action == 'Requested':
            tickets.append((ticket_id, customer_id, order_id, f'The {item[3]} is defective or unwanted. Please process my request.', 'Open', (today - timedelta(days=random.randint(0, 2))).isoformat(), ticket_type))
            ticket_id += 1
        elif refund_action == 'Processed':
            tickets.append((ticket_id, customer_id, order_id, f'Returned/Replaced {item[3]} successfully.', 'Closed', (today - timedelta(days=random.randint(5, 10))).isoformat(), ticket_type))
            ticket_id += 1
        elif refund_action == 'Rejected':
            tickets.append((ticket_id, customer_id, order_id, f'Why was my request for {item[3]} rejected?', 'Closed', (today - timedelta(days=random.randint(1, 20))).isoformat(), ticket_type))
            ticket_id += 1

        orders.append((order_id, customer_id, i_id, quantity, order_date.isoformat(), delivery_date.isoformat(), total_amount, payment, refund_status))

    with open(os.path.join(csv_dir, 'orders.csv'), 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['order_id', 'customer_id', 'item_id', 'quantity', 'order_date', 'delivery_date', 'total_amount', 'payment_method', 'refund_status'])
        writer.writerows(orders)

    # 4. Write Support Tickets
    with open(os.path.join(csv_dir, 'support_tickets.csv'), 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['ticket_id', 'customer_id', 'order_id', 'issue_description', 'status', 'created_at', 'ticket_type'])
        writer.writerows(tickets)
        
    print(f"Successfully generated CSV files in {os.path.abspath(csv_dir)}")
    print(f"Generated 15 customers, {len(items)} items, 250 orders, and {len(tickets)} support tickets.")

if __name__ == "__main__":
    generate_mock_data()
