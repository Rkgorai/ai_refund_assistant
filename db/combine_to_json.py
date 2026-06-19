import csv
import json
import os

def load_csv(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def combine():
    # Ensure paths are correct
    base_dir = os.path.dirname(os.path.abspath(__file__))
    customers_path = os.path.join(base_dir, 'csv_data', 'customers.csv')
    orders_path = os.path.join(base_dir, 'csv_data', 'orders.csv')
    items_path = os.path.join(base_dir, 'csv_data', 'items.csv')
    output_path = os.path.join(base_dir, 'combined_data.json')

    customers = load_csv(customers_path)
    orders = load_csv(orders_path)
    items = load_csv(items_path)
    
    # Create item lookup dictionary
    items_dict = {item['item_id']: item for item in items}
    
    # Create customer lookup with empty orders list
    customers_dict = {}
    for c in customers:
        # Create a clean copy to avoid modifying original CSV directly
        c_clean = {k: v for k, v in c.items()}
        c_clean['orders'] = []
        customers_dict[c['customer_id']] = c_clean
        
    # Append orders (and their corresponding items) to customers
    for o in orders:
        c_id = o['customer_id']
        i_id = o['item_id']
        
        order_details = {
            'order_id': o['order_id'],
            'order_date': o['order_date'],
            'delivery_date': o['delivery_date'],
            'refund_status': o['refund_status'],
            'item': items_dict.get(i_id, {})
        }
        
        if c_id in customers_dict:
            customers_dict[c_id]['orders'].append(order_details)
            
    # Convert back to a list for JSON
    combined_data = list(customers_dict.values())
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(combined_data, f, indent=4)
        
    print(f"Successfully merged {len(customers)} customers and their orders into {output_path}")

if __name__ == "__main__":
    combine()
