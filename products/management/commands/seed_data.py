"""
Management command: python manage.py seed_data [--products 2000] [--warm 0]

Seeds everything needed for a fresh clone to be immediately usable:
  1. The 5 demo platforms (with simulated delivery-fee data).
  2. A Karnataka geography: State -> District -> City -> Locality, covering
     the major population centers listed in the project brief. This is a
     representative dataset, not exhaustive coverage (see README).
  3. PlatformAvailability per locality - a simple, explainable tiering
     (metro Bengaluru gets all 5 platforms; other major cities get the
     three lighter-footprint ones; smaller towns get one or none), which
     is itself simulated and documented as such.
  4. The product catalog: generates products/taxonomy.py's templates to
     JSON and imports them via the same idempotent import_products
     command a real data pipeline would use.

Offers/prices are deliberately NOT pre-generated here - see
products/pricing.py for why (lazy materialization at this catalog size).
Use --warm to pre-materialize a few for immediate demoing without
browsing first.

Safe to re-run: everything is get_or_create / idempotent-import based.
"""

from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand

from products.models import City, District, Locality, Platform, PlatformAvailability, Product, State

PLATFORM_SEED = [
    {"name": "Blinkit", "slug": "blinkit", "primary_color": "#f8cb46", "base_url": "https://blinkit.com",
     "base_delivery_fee": Decimal("15.00"), "free_delivery_above": Decimal("199.00")},
    {"name": "Zepto", "slug": "zepto", "primary_color": "#8b2fc9", "base_url": "https://www.zeptonow.com",
     "base_delivery_fee": Decimal("19.00"), "free_delivery_above": Decimal("199.00")},
    {"name": "Swiggy Instamart", "slug": "swiggy-instamart", "primary_color": "#fc8019", "base_url": "https://www.swiggy.com/instamart",
     "base_delivery_fee": Decimal("25.00"), "free_delivery_above": Decimal("249.00")},
    {"name": "Flipkart Minutes", "slug": "flipkart-minutes", "primary_color": "#2874f0", "base_url": "https://www.flipkart.com/minutes",
     "base_delivery_fee": Decimal("22.00"), "free_delivery_above": Decimal("249.00")},
    {"name": "BigBasket", "slug": "bigbasket", "primary_color": "#84c225", "base_url": "https://www.bigbasket.com",
     "base_delivery_fee": Decimal("30.00"), "free_delivery_above": Decimal("299.00")},
]

# District -> [cities]. Real Karnataka district/city relationships
# (twin cities Hubballi-Dharwad share a district; Hosapete sits in
# Ballari district), covering the population centers named in the brief.
DISTRICT_CITY_MAP = {
    "Bengaluru Urban": ["Bengaluru"],
    "Mysuru": ["Mysuru"],
    "Dakshina Kannada": ["Mangaluru"],
    "Dharwad": ["Hubballi", "Dharwad"],
    "Belagavi": ["Belagavi"],
    "Kalaburagi": ["Kalaburagi"],
    "Davanagere": ["Davanagere"],
    "Ballari": ["Ballari", "Hosapete"],
    "Shivamogga": ["Shivamogga"],
    "Tumakuru": ["Tumakuru"],
    "Udupi": ["Udupi"],
    "Vijayapura": ["Vijayapura"],
    "Hassan": ["Hassan"],
    "Mandya": ["Mandya"],
    "Chikkamagaluru": ["Chikkamagaluru"],
    "Kolar": ["Kolar"],
    "Bidar": ["Bidar"],
    "Raichur": ["Raichur"],
    "Koppal": ["Koppal"],
    "Chitradurga": ["Chitradurga"],
    "Bagalkot": ["Bagalkot"],
    "Gadag": ["Gadag"],
    "Yadgir": ["Yadgir"],
    "Ramanagara": ["Ramanagara"],
    "Chamarajanagar": ["Chamarajanagar"],
    "Kodagu": ["Madikeri"],
}

# City -> [(locality, pincode)]. Pincodes are only filled in where
# reasonably well-known (major Bengaluru localities); left blank
# elsewhere rather than guessed - see README "Karnataka location system".
LOCALITY_MAP = {
    "Bengaluru": [
        ("Koramangala", "560034"), ("Indiranagar", "560038"), ("HSR Layout", "560102"),
        ("Whitefield", "560066"), ("Bellandur", "560103"), ("Marathahalli", "560037"),
        ("Electronic City", "560100"), ("Jayanagar", "560041"), ("Hebbal", "560024"),
        ("Yelahanka", "560064"),
    ],
    "Mysuru": [("Vijayanagar", ""), ("Saraswathipuram", "")],
    "Mangaluru": [("Kadri", ""), ("Kankanady", "")],
    "Hubballi": [("Vidyanagar", ""), ("Gokul Road", "")],
    "Dharwad": [("Malmaddi", ""), ("Saptapur", "")],
    "Belagavi": [("Tilakwadi", ""), ("Camp", "")],
    "Kalaburagi": [("Sedam Road", ""), ("Ashok Nagar", "")],
    "Davanagere": [("P J Extension", ""), ("Vidyanagar", "")],
    "Ballari": [("Gandhinagar", ""), ("Cowl Bazaar", "")],
    "Hosapete": [("Station Road", "")],
    "Shivamogga": [("Vinoba Nagar", ""), ("Gopala Extension", "")],
    "Tumakuru": [("Batwadi", ""), ("SS Puram", "")],
    "Udupi": [("Manipal", ""), ("Malpe", "")],
    "Vijayapura": [("Jalnagar", ""), ("Station Road", "")],
    "Hassan": [("BM Road", "")],
    "Mandya": [("Vidyanagar", "")],
    "Chikkamagaluru": [("MG Road", "")],
    "Kolar": [("MB Road", "")],
    "Bidar": [("Old Bidar", "")],
    "Raichur": [("Station Road", "")],
    "Koppal": [("Gandhi Nagar", "")],
    "Chitradurga": [("SJM Nagar", "")],
    "Bagalkot": [("Vidyagiri", "")],
    "Gadag": [("Station Road", "")],
    "Yadgir": [("Gandhi Nagar", "")],
    "Ramanagara": [("IG Road", "")],
    "Chamarajanagar": [("Bangalore Road", "")],
    "Madikeri": [("School Barracks", "")],
}

# City -> platforms available there. A simple, explainable tiering
# standing in for real coverage data (metro gets everything; other major
# cities get the three lighter-footprint platforms; small towns get one).
# See README "Platform availability by location".
TIER_1_ALL_PLATFORMS = {"Bengaluru"}
TIER_2_THREE_PLATFORMS = {
    "Mysuru", "Mangaluru", "Hubballi", "Dharwad", "Belagavi", "Kalaburagi",
    "Davanagere", "Ballari", "Shivamogga", "Tumakuru", "Udupi",
}
TIER_2_PLATFORMS = {"Blinkit", "Zepto", "Swiggy Instamart"}
TIER_3_ONE_PLATFORM = {"Blinkit"}


class Command(BaseCommand):
    help = "Seed platforms, the Karnataka location hierarchy, platform availability, and the product catalog."

    def add_arguments(self, parser):
        parser.add_argument("--products", type=int, default=2000, help="Target minimum number of products.")
        parser.add_argument("--warm", type=int, default=0, help="Pre-materialize offers for N products (see refresh_prices --warm).")

    def handle(self, *args, **options):
        self._seed_platforms()
        self._seed_karnataka()
        self._seed_availability()
        self._seed_catalog(options["products"])
        self._seed_images()

        if options["warm"]:
            call_command("refresh_prices", warm=options["warm"])

        self.stdout.write(self.style.SUCCESS(
            f"Seed complete. {Product.objects.count()} product(s), "
            f"{Locality.objects.count()} localit(y/ies) across {City.objects.count()} cities in Karnataka, "
            f"{Platform.objects.count()} platform(s)."
        ))

    def _seed_platforms(self):
        for entry in PLATFORM_SEED:
            Platform.objects.update_or_create(name=entry["name"], defaults=entry)
        self.stdout.write(f"Platforms: {Platform.objects.count()}")

    def _seed_karnataka(self):
        state, _ = State.objects.get_or_create(name="Karnataka", defaults={"code": "KA"})
        for district_name, cities in DISTRICT_CITY_MAP.items():
            district, _ = District.objects.get_or_create(state=state, name=district_name)
            for city_name in cities:
                city, _ = City.objects.get_or_create(district=district, name=city_name)
                localities = LOCALITY_MAP.get(city_name, [(f"{city_name} Town Centre", "")])
                for locality_name, pincode in localities:
                    Locality.objects.get_or_create(city=city, name=locality_name, defaults={"pincode": pincode})
        self.stdout.write(
            f"Karnataka: {District.objects.count()} district(s), {City.objects.count()} cit(y/ies), "
            f"{Locality.objects.count()} localit(y/ies)"
        )

    def _seed_availability(self):
        platforms_by_name = {p.name: p for p in Platform.objects.all()}
        count = 0
        for locality in Locality.objects.select_related("city"):
            city_name = locality.city.name
            if city_name in TIER_1_ALL_PLATFORMS:
                available_names = set(platforms_by_name)
            elif city_name in TIER_2_THREE_PLATFORMS:
                available_names = TIER_2_PLATFORMS
            else:
                available_names = TIER_3_ONE_PLATFORM

            for name, platform in platforms_by_name.items():
                status = PlatformAvailability.AVAILABLE if name in available_names else PlatformAvailability.UNAVAILABLE
                PlatformAvailability.objects.update_or_create(
                    platform=platform, locality=locality, defaults={"status": status}
                )
                count += 1
        self.stdout.write(f"Platform availability: {count} (platform, locality) pair(s) set")

    def _seed_catalog(self, target: int):
        if Product.objects.filter(is_active=True).count() >= target:
            self.stdout.write(f"Catalog already has {Product.objects.count()} products (target {target}) - skipping generation.")
            return
        out_path = "fixtures/generated_products.json"
        call_command("generate_catalog", out=out_path)
        call_command("import_products", out_path)
        self.stdout.write(f"Catalog: {Product.objects.count()} product(s)")

    def _seed_images(self):
        call_command("generate_product_images")
