"""
Category/subcategory taxonomy and the generation templates used by
`manage.py generate_catalog` to build a realistic demo product catalog.

Design note: rather than hand-writing 2000+ individual product literals
(which the project brief explicitly asks to avoid), each template
describes one *slice* of the catalog as brands x variants x sizes, and
the generator (products/management/commands/generate_catalog.py) expands
the cross product into individual product records. This keeps the data
here compact (a few short lists per subcategory) while still producing
specific, realistic names like "Amul Taaza Toned Milk 1L" rather than
"Product 4821".

Each template:
    category:     top-level category name (Category model)
    subcategory:  leaf subcategory name (Subcategory model)
    base_name:    the generic product name, e.g. "Basmati Rice" (may be
                  "" for produce, where the variant IS the item name)
    brands:       real/realistic brand names (or quality tags for produce
                  like "Fresh", "Farm Fresh")
    variants:     flavor/type descriptors; "" means no variant suffix
    sizes:        size strings parsed by products/normalization.py
                  (e.g. "1kg", "500ml", "6 pcs")

name assembly: "{brand} {variant} {base_name} {size}" with empty parts
skipped, e.g. brand="Lays" variant="Masala" base_name="Chips"
size="52g" -> "Lays Masala Chips 52g".
"""

TEMPLATES = [
    # ---------------- GROCERY & STAPLES ----------------
    {"category": "Grocery & Staples", "subcategory": "Rice", "base_name": "Basmati Rice",
     "brands": ["India Gate", "Kohinoor", "Daawat", "Fortune"],
     "variants": ["", "Classic", "Extra Long Grain", "Steam"],
     "sizes": ["1kg", "5kg", "10kg"]},
    {"category": "Grocery & Staples", "subcategory": "Atta & Flour", "base_name": "Atta",
     "brands": ["Aashirvaad", "Pillsbury", "Fortune", "Annapurna"],
     "variants": ["Whole Wheat", "Multigrain", "Select", ""],
     "sizes": ["1kg", "5kg", "10kg"]},
    {"category": "Grocery & Staples", "subcategory": "Pulses & Dal", "base_name": "",
     "brands": ["Tata Sampann", "Fortune", "Local", "24 Mantra"],
     "variants": ["Toor Dal", "Moong Dal", "Chana Dal", "Masoor Dal", "Urad Dal"],
     "sizes": ["500g", "1kg", "2kg"]},
    {"category": "Grocery & Staples", "subcategory": "Edible Oils", "base_name": "Oil",
     "brands": ["Fortune", "Saffola", "Sundrop", "Dhara"],
     "variants": ["Sunflower", "Groundnut", "Mustard", "Rice Bran"],
     "sizes": ["1L", "2L", "5L"]},
    {"category": "Grocery & Staples", "subcategory": "Ghee", "base_name": "Ghee",
     "brands": ["Amul", "Patanjali", "Nandini", "Mother Dairy"],
     "variants": ["Pure", "Cow", ""],
     "sizes": ["200ml", "500ml", "1L"]},
    {"category": "Grocery & Staples", "subcategory": "Spices", "base_name": "Powder",
     "brands": ["MDH", "Everest", "Catch", "Badshah"],
     "variants": ["Turmeric", "Red Chilli", "Coriander", "Garam Masala", "Cumin"],
     "sizes": ["100g", "200g", "500g"]},
    {"category": "Grocery & Staples", "subcategory": "Salt", "base_name": "Salt",
     "brands": ["Tata", "Aashirvaad", "Catch", "Annapurna"],
     "variants": ["Iodized", "Rock", "Black", ""],
     "sizes": ["500g", "1kg"]},
    {"category": "Grocery & Staples", "subcategory": "Sugar", "base_name": "Sugar",
     "brands": ["Madhur", "Dhampure", "Local", "Uttam"],
     "variants": ["White", "Brown", ""],
     "sizes": ["500g", "1kg", "5kg"]},
    {"category": "Grocery & Staples", "subcategory": "Dry Fruits", "base_name": "",
     "brands": ["Happilo", "Nutraj", "Tulsi", "Local"],
     "variants": ["Almonds", "Cashews", "Raisins", "Walnuts", "Pistachios"],
     "sizes": ["100g", "250g", "500g"]},

    # ---------------- DAIRY & BREAKFAST ----------------
    {"category": "Dairy & Breakfast", "subcategory": "Milk", "base_name": "Milk",
     "brands": ["Amul", "Nandini", "Heritage", "Mother Dairy"],
     "variants": ["Taaza Toned", "Gold Full Cream", "Slim", ""],
     "sizes": ["500ml", "1L"]},
    {"category": "Dairy & Breakfast", "subcategory": "Curd", "base_name": "Curd",
     "brands": ["Amul", "Nandini", "Nestle", "Mother Dairy"],
     "variants": ["Fresh", "Set", ""],
     "sizes": ["200g", "400g", "1kg"]},
    {"category": "Dairy & Breakfast", "subcategory": "Paneer", "base_name": "Paneer",
     "brands": ["Amul", "Mother Dairy", "Nandini", "Gowardhan"],
     "variants": ["Fresh", "Malai", ""],
     "sizes": ["200g", "400g"]},
    {"category": "Dairy & Breakfast", "subcategory": "Cheese", "base_name": "Cheese",
     "brands": ["Amul", "Britannia", "Go Cheese", "Dlecta"],
     "variants": ["Slices", "Cubes", "Spread", "Mozzarella"],
     "sizes": ["100g", "200g", "400g"]},
    {"category": "Dairy & Breakfast", "subcategory": "Butter", "base_name": "Butter",
     "brands": ["Amul", "Britannia", "Nandini", "Mother Dairy"],
     "variants": ["Salted", "Unsalted", ""],
     "sizes": ["100g", "500g"]},
    {"category": "Dairy & Breakfast", "subcategory": "Eggs", "base_name": "Eggs",
     "brands": ["Farm Fresh", "Happy Hens", "Local", "Keggs"],
     "variants": ["White", "Brown", "Free Range"],
     "sizes": ["6 pcs", "12 pcs", "30 pcs"]},
    {"category": "Dairy & Breakfast", "subcategory": "Bread", "base_name": "Bread",
     "brands": ["Britannia", "Modern", "Harvest Gold", "English Oven"],
     "variants": ["White", "Brown", "Multigrain", "Milk"],
     "sizes": ["350g", "400g", "600g"]},
    {"category": "Dairy & Breakfast", "subcategory": "Bakery", "base_name": "",
     "brands": ["Britannia", "Monginis", "Local Bakery", "Harvest Gold"],
     "variants": ["Bun Pack", "Pav", "Rusk", "Cake Slice"],
     "sizes": ["200g", "300g", "400g"]},
    {"category": "Dairy & Breakfast", "subcategory": "Cereals", "base_name": "",
     "brands": ["Kellogg's", "Bagrry's", "Quaker", "Saffola"],
     "variants": ["Corn Flakes", "Muesli", "Oats", "Chocos"],
     "sizes": ["250g", "500g", "1kg"]},
    {"category": "Dairy & Breakfast", "subcategory": "Breakfast Foods", "base_name": "",
     "brands": ["MTR", "Gits", "Bambino", "Local"],
     "variants": ["Poha", "Upma Mix", "Rava Idli Mix", "Vermicelli"],
     "sizes": ["200g", "500g", "1kg"]},

    # ---------------- SNACKS & PACKAGED FOOD ----------------
    {"category": "Snacks & Packaged Food", "subcategory": "Chips", "base_name": "Chips",
     "brands": ["Lays", "Bingo", "Kurkure", "Haldiram's"],
     "variants": ["Classic Salted", "Masala Munch", "Tomato Twist", "Sour Cream & Onion"],
     "sizes": ["52g", "90g", "150g"]},
    {"category": "Snacks & Packaged Food", "subcategory": "Namkeen", "base_name": "",
     "brands": ["Haldiram's", "Bikaji", "Balaji", "Local"],
     "variants": ["Bhujia", "Aloo Bhujia", "Mixture", "Chivda"],
     "sizes": ["150g", "200g", "400g"]},
    {"category": "Snacks & Packaged Food", "subcategory": "Biscuits", "base_name": "",
     "brands": ["Britannia", "Parle", "Sunfeast", "Unibic"],
     "variants": ["Marie Gold", "Good Day", "Milk Bikis", "Digestive"],
     "sizes": ["100g", "200g", "375g"]},
    {"category": "Snacks & Packaged Food", "subcategory": "Chocolates", "base_name": "",
     "brands": ["Cadbury", "Nestle", "Amul", "Ferrero"],
     "variants": ["Dairy Milk", "KitKat", "Munch", "Dark Chocolate"],
     "sizes": ["13g", "55g", "150g"]},
    {"category": "Snacks & Packaged Food", "subcategory": "Instant Noodles", "base_name": "Noodles",
     "brands": ["Maggi", "Top Ramen", "Yippee", "Ching's"],
     "variants": ["Masala", "Chicken", "Veg Atta", ""],
     "sizes": ["70g", "140g", "280g"]},
    {"category": "Snacks & Packaged Food", "subcategory": "Pasta", "base_name": "Pasta",
     "brands": ["Weikfield", "Del Monte", "Sunfeast", "Chings"],
     "variants": ["Penne", "Fusilli", "Macaroni", ""],
     "sizes": ["200g", "400g"]},
    {"category": "Snacks & Packaged Food", "subcategory": "Sauces", "base_name": "Sauce",
     "brands": ["Kissan", "Maggi", "Ching's", "Del Monte"],
     "variants": ["Tomato Ketchup", "Chilli Sauce", "Soy Sauce", "Schezwan"],
     "sizes": ["200g", "500g", "1kg"]},
    {"category": "Snacks & Packaged Food", "subcategory": "Spreads", "base_name": "",
     "brands": ["Nutella", "Kissan", "Sundrop", "Doon Valley"],
     "variants": ["Chocolate Spread", "Peanut Butter", "Mixed Fruit Jam", "Honey"],
     "sizes": ["200g", "350g", "700g"]},
    {"category": "Snacks & Packaged Food", "subcategory": "Ready-to-Eat", "base_name": "",
     "brands": ["MTR", "Haldiram's", "Gits", "ITC"],
     "variants": ["Rajma", "Dal Makhani", "Paneer Butter Masala", "Veg Pulao"],
     "sizes": ["285g", "300g"]},

    # ---------------- BEVERAGES ----------------
    {"category": "Beverages", "subcategory": "Water", "base_name": "Packaged Drinking Water",
     "brands": ["Bisleri", "Aquafina", "Kinley", "Himalayan"],
     "variants": [""],
     "sizes": ["500ml", "1L", "2L"]},
    {"category": "Beverages", "subcategory": "Soft Drinks", "base_name": "",
     "brands": ["Coca-Cola", "Pepsi", "Sprite", "Thums Up"],
     "variants": ["Regular", "Zero Sugar", ""],
     "sizes": ["250ml", "750ml", "1.25L"]},
    {"category": "Beverages", "subcategory": "Juices", "base_name": "Juice",
     "brands": ["Real", "Tropicana", "Paper Boat", "B Natural"],
     "variants": ["Mixed Fruit", "Orange", "Mango", "Guava"],
     "sizes": ["200ml", "1L"]},
    {"category": "Beverages", "subcategory": "Tea", "base_name": "Tea",
     "brands": ["Red Label", "Tata Tea", "Society", "Lipton"],
     "variants": ["Gold", "Premium", "Green", ""],
     "sizes": ["100g", "250g", "500g"]},
    {"category": "Beverages", "subcategory": "Coffee", "base_name": "Coffee",
     "brands": ["Nescafe", "Bru", "Continental", "Davidoff"],
     "variants": ["Classic", "Instant", "Filter", ""],
     "sizes": ["50g", "100g", "200g"]},
    {"category": "Beverages", "subcategory": "Energy Drinks", "base_name": "",
     "brands": ["Red Bull", "Monster", "Sting", "Gatorade"],
     "variants": ["Original", "Sugar-Free", ""],
     "sizes": ["250ml", "500ml"]},

    # ---------------- FRUITS & VEGETABLES ----------------
    {"category": "Fruits & Vegetables", "subcategory": "Vegetables", "base_name": "",
     "brands": ["Fresh", "Farm Fresh", "Organic"],
     "variants": ["Onion", "Tomato", "Potato", "Carrot", "Cabbage", "Spinach", "Capsicum", "Cucumber"],
     "sizes": ["500g", "1kg"]},
    {"category": "Fruits & Vegetables", "subcategory": "Fruits", "base_name": "",
     "brands": ["Fresh", "Farm Fresh", "Organic"],
     "variants": ["Banana", "Apple", "Mango", "Grapes", "Papaya", "Orange", "Pomegranate", "Watermelon"],
     "sizes": ["500g", "1kg"]},

    # ---------------- FROZEN FOOD ----------------
    {"category": "Frozen Food", "subcategory": "Frozen Snacks", "base_name": "",
     "brands": ["McCain", "ITC", "Godrej Yummiez", "Sumeru"],
     "variants": ["French Fries", "Veg Nuggets", "Chicken Nuggets", "Aloo Tikki"],
     "sizes": ["200g", "425g", "750g"]},
    {"category": "Frozen Food", "subcategory": "Frozen Vegetables", "base_name": "Frozen",
     "brands": ["Safal", "McCain", "Godrej", "Local"],
     "variants": ["Green Peas", "Mixed Vegetables", "Sweet Corn", "Spinach"],
     "sizes": ["200g", "500g"]},
    {"category": "Frozen Food", "subcategory": "Ice Cream", "base_name": "Ice Cream",
     "brands": ["Amul", "Kwality Walls", "Baskin Robbins", "Havmor"],
     "variants": ["Vanilla", "Chocolate", "Butterscotch", "Kesar Pista"],
     "sizes": ["125ml", "500ml", "1L"]},

    # ---------------- PERSONAL CARE ----------------
    {"category": "Personal Care", "subcategory": "Bath & Body", "base_name": "Soap",
     "brands": ["Dove", "Lux", "Pears", "Santoor"],
     "variants": ["Moisturizing", "Glycerin", "Sandal", ""],
     "sizes": ["75g", "100g", "125g"]},
    {"category": "Personal Care", "subcategory": "Skin Care", "base_name": "",
     "brands": ["Nivea", "Ponds", "Himalaya", "Cetaphil"],
     "variants": ["Face Wash", "Moisturizer", "Sunscreen", "Body Lotion"],
     "sizes": ["50g", "100ml", "200ml"]},
    {"category": "Personal Care", "subcategory": "Hair Care", "base_name": "",
     "brands": ["Head & Shoulders", "Dove", "Sunsilk", "Pantene"],
     "variants": ["Shampoo", "Conditioner", "Hair Oil", "Anti-Dandruff Shampoo"],
     "sizes": ["90ml", "180ml", "340ml"]},
    {"category": "Personal Care", "subcategory": "Oral Care", "base_name": "",
     "brands": ["Colgate", "Sensodyne", "Pepsodent", "Closeup"],
     "variants": ["Toothpaste", "Toothbrush", "Mouthwash", ""],
     "sizes": ["80g", "150g", "200g"]},
    {"category": "Personal Care", "subcategory": "Deodorants", "base_name": "",
     "brands": ["Axe", "Nivea", "Fogg", "Park Avenue"],
     "variants": ["Deo Spray", "Roll-On", "Body Mist", ""],
     "sizes": ["50ml", "150ml"]},
    {"category": "Personal Care", "subcategory": "Grooming", "base_name": "",
     "brands": ["Gillette", "Bombay Shaving Company", "Philips", "Nivea Men"],
     "variants": ["Razor", "Shaving Gel", "Aftershave", "Trimmer"],
     "sizes": ["1 pcs", "100ml", "200ml"]},

    # ---------------- BABY CARE ----------------
    {"category": "Baby Care", "subcategory": "Diapers", "base_name": "Baby Diapers",
     "brands": ["Pampers", "Huggies", "MamyPoko", "Sirona"],
     "variants": ["Small", "Medium", "Large", "XL"],
     "sizes": ["20 pcs", "42 pcs", "62 pcs"]},
    {"category": "Baby Care", "subcategory": "Baby Food", "base_name": "",
     "brands": ["Cerelac", "Farex", "Nestle", "Himalaya"],
     "variants": ["Wheat Cereal", "Rice Cereal", "Multigrain", ""],
     "sizes": ["200g", "300g"]},
    {"category": "Baby Care", "subcategory": "Baby Hygiene", "base_name": "",
     "brands": ["Johnson's", "Himalaya", "Sebamed", "Mamaearth"],
     "variants": ["Baby Wipes", "Baby Lotion", "Baby Shampoo", "Baby Powder"],
     "sizes": ["50g", "100ml", "200ml"]},

    # ---------------- HOUSEHOLD ----------------
    {"category": "Household", "subcategory": "Laundry", "base_name": "Detergent",
     "brands": ["Surf Excel", "Ariel", "Tide", "Rin"],
     "variants": ["Matic Liquid", "Powder", "Bar", ""],
     "sizes": ["500g", "1kg", "2L"]},
    {"category": "Household", "subcategory": "Dishwashing", "base_name": "",
     "brands": ["Vim", "Pril", "Exo", "Godrej Protekt"],
     "variants": ["Dishwash Gel", "Dishwash Bar", "Dishwash Powder", ""],
     "sizes": ["200g", "500ml", "1L"]},
    {"category": "Household", "subcategory": "Home Cleaning", "base_name": "",
     "brands": ["Harpic", "Lizol", "Domex", "Colin"],
     "variants": ["Toilet Cleaner", "Floor Cleaner", "Glass Cleaner", ""],
     "sizes": ["200ml", "500ml", "1L"]},
    {"category": "Household", "subcategory": "Kitchen Cleaning", "base_name": "",
     "brands": ["Vim", "Scotch-Brite", "3M", "Cif"],
     "variants": ["Scrub Pad", "Steel Scrubber", "Kitchen Wipes", ""],
     "sizes": ["1 pcs", "2 pcs", "5 pcs"]},
    {"category": "Household", "subcategory": "Paper Products", "base_name": "",
     "brands": ["Origami", "Century", "Freshia", "Premier"],
     "variants": ["Tissue Paper", "Kitchen Towel", "Toilet Roll", ""],
     "sizes": ["1 pcs", "2 pcs", "4 pcs"]},
    {"category": "Household", "subcategory": "Garbage Bags", "base_name": "Garbage Bags",
     "brands": ["Novelty", "Precept", "All Time", "Local"],
     "variants": ["Small", "Medium", "Large", "XL"],
     "sizes": ["15 pcs", "30 pcs", "60 pcs"]},

    # ---------------- PET CARE ----------------
    {"category": "Pet Care", "subcategory": "Pet Food", "base_name": "",
     "brands": ["Pedigree", "Whiskas", "Drools", "Royal Canin"],
     "variants": ["Adult Dog Food", "Puppy Food", "Cat Food", "Treats"],
     "sizes": ["400g", "1.2kg", "3kg"]},
    {"category": "Pet Care", "subcategory": "Pet Accessories", "base_name": "",
     "brands": ["Trixie", "PetSafe", "Kennel Club", "Local"],
     "variants": ["Leash", "Collar", "Food Bowl", "Chew Toy"],
     "sizes": ["1 pcs"]},

    # ---------------- HOME & KITCHEN ----------------
    {"category": "Home & Kitchen", "subcategory": "Kitchen Tools", "base_name": "",
     "brands": ["Prestige", "Pigeon", "Milton", "Borosil"],
     "variants": ["Knife Set", "Chopping Board", "Non-Stick Pan", "Steel Container"],
     "sizes": ["1 pcs"]},
    {"category": "Home & Kitchen", "subcategory": "Storage", "base_name": "",
     "brands": ["Milton", "Cello", "Tupperware", "Signoraware"],
     "variants": ["Airtight Container", "Water Bottle", "Lunch Box", "Storage Jar"],
     "sizes": ["1 pcs", "500ml", "1L"]},

    # ---------------- STATIONERY ----------------
    {"category": "Stationery", "subcategory": "Stationery", "base_name": "",
     "brands": ["Classmate", "Camlin", "Reynolds", "Parker"],
     "variants": ["Notebook", "Ball Pen Pack", "Pencil Box", "Sketch Pens"],
     "sizes": ["1 pcs", "5 pcs", "10 pcs"]},

    # ---------------- ELECTRONICS / ACCESSORIES ----------------
    {"category": "Electronics & Accessories", "subcategory": "Batteries", "base_name": "Batteries",
     "brands": ["Duracell", "Eveready", "Energizer", "Amazon Basics"],
     "variants": ["AA", "AAA", "9V", ""],
     "sizes": ["2 pcs", "4 pcs", "8 pcs"]},
    {"category": "Electronics & Accessories", "subcategory": "Chargers & Cables", "base_name": "",
     "brands": ["boAt", "Portronics", "Ambrane", "Amazon Basics"],
     "variants": ["USB-C Cable", "Charger Adapter", "Lightning Cable", "Power Bank"],
     "sizes": ["1 pcs"]},
    {"category": "Electronics & Accessories", "subcategory": "Small Accessories", "base_name": "",
     "brands": ["boAt", "Zebronics", "Portronics", "Local"],
     "variants": ["Earphones", "Phone Stand", "Mouse", "Screen Protector"],
     "sizes": ["1 pcs"]},
]


def expected_product_count() -> int:
    """The number of products TEMPLATES will generate, before dedup -
    used by tests and the generate_catalog command to sanity-check output."""
    total = 0
    for t in TEMPLATES:
        total += len(t["brands"]) * len(t["variants"]) * len(t["sizes"])
    return total
