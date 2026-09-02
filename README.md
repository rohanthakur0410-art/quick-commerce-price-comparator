# QuickCart — Quick-Commerce Price Intelligence Platform

**Compare quick-commerce prices near you and buy smarter.**

QuickCart is a Django + Django REST Framework backend and web UI that answers,
for any product and any Karnataka locality: *which platform has it cheapest
right now, and is it even worth splitting my order to save money?*

## Overview

### Problem
Quick-commerce prices, availability, and delivery times differ by platform
*and* by delivery area, and they change through the day. Comparing five
apps by hand doesn't scale, and a naive "biggest catalog wins" demo doesn't
reflect how real pricing works — price is never a property of a product
alone.

### Solution
A canonical product catalog (2,500+ realistic SKUs) decoupled from
platform-specific pricing; a Karnataka location hierarchy that scopes every
price to where it's actually valid; a provider layer that prices a product
for a platform *without* the comparison engine knowing or caring how; and a
basket engine that explains, in plain language, whether buying everything
from one platform or splitting across two is actually cheaper once delivery
fees are counted.

## Architecture

```text
USER
 |
 v
LOCATION SELECTION  (State -> District -> City -> Locality)
 |
 v
PRODUCT SEARCH  (indexed DB query - never a full-table Python scan)
 |
 v
CANONICAL PRODUCT  (products.models.Product - brand/name/qty/unit, no price)
 |
 v
PLATFORM PROVIDERS  (scrapers/ - one adapter per platform, demo-simulated)
 |
 v
NORMALIZED OFFERS  (ProductOffer: product + platform + locality + price +
                     availability + promotion + timestamp)
 |
 v
PRICE / AVAILABILITY ENGINE  (products/pricing.py - lazy materialization,
                               fail-closed PlatformAvailability)
 |
 v
COMPARISON ENGINE  (products/services.py: compare_prices, insights)
 |
 v
DEAL OPTIMIZATION ENGINE  (products/services.py: compare_basket - single
                            -platform totals, cross-platform split, savings
                            explanation)
 |
 v
QUICKCART UI  (paginated search, category browse, product page, basket)
```

Each layer only talks to the one below it through a narrow interface:
the comparison engine never touches HTML/scraping details (that's entirely
inside `scrapers/`), and the UI/API never compute a price themselves (that's
entirely inside `products/services.py`).

## Database Design

```text
State --< District --< City --< Locality >-- PlatformAvailability >-- Platform
                                    |                                     |
                                    +--------------< ProductOffer >-------+
                                                          |
                                                     PriceHistory
                                                          |
                                    Product >-- Subcategory >-- Category
```

| Model | Purpose |
|---|---|
| `State` / `District` / `City` / `Locality` | The geography hierarchy. Karnataka only for now; adding a state is new rows (see "How to add another state"). |
| `Platform` | A quick-commerce platform, read from the DB - never hard-coded in a view or template. Carries simulated `base_delivery_fee`/`free_delivery_above`. |
| `PlatformAvailability` | Whether a platform services a locality at all. **Fail-closed**: no row (or a non-"available" row) means the platform is never shown there, full stop. |
| `Category` / `Subcategory` | The product taxonomy (13 categories, 62 subcategories - see products/taxonomy.py). |
| `Product` | The canonical product. Has **no price field** - price belongs to `ProductOffer`. Unique on `(brand, normalized_name, quantity, unit)`. |
| `ProductOffer` | One product's live listing on one platform, in one locality: price, availability, delivery estimate, promotion, `is_demo`, `last_checked_at`. |
| `PriceHistory` | An immutable row per *observed change* to a `ProductOffer` (see "Dynamic pricing" below). |

### Why Product/Platform/Location are separate
A price is never a property of a product alone: the same product's price
depends on which platform quotes it and which locality that quote is valid
for. Modeling them as independent entities joined by `ProductOffer` means a
new platform is a row + one adapter class, a new locality is a row, and the
comparison query can never accidentally mix a Bengaluru price with a Mysuru
one - that mixing would require an explicit join across the wrong FK, and
`compare_prices()` never does that.

### Indexing decisions
- `Product.name` / `.brand` / `.normalized_name` — support search across all
  three without a full scan, at 2,500+ rows and growing.
- `Product(brand, normalized_name, quantity, unit)` — the *unique
  constraint* doubling as the dedup key ingestion matches against.
- `ProductOffer(product, locality)` — the core comparison query.
- `ProductOffer(platform, locality)` — platform/locality browsing.
- `ProductOffer(is_available, current_price)` — "cheapest available offer."
- `PlatformAvailability(locality, status)` — "which platforms serve this
  locality," checked on every comparison.
- `PriceHistory(product_offer, -recorded_at)` — "history for this offer,
  most recent first," used by `/history/` and price-insight calculations.
- `Locality(city, name)` / `Locality(pincode)` — the location picker's
  search-by-locality/city/pincode query.

## Karnataka location system

28 cities across 26 districts, 49 localities total (Bengaluru gets 10; most
other cities get 1-2 representative localities - **this is a
representative sample, not exhaustive coverage**, and the README says so
rather than implying otherwise). Pincodes are only filled in where
reasonably well-known (major Bengaluru localities); left blank elsewhere
rather than guessed.

Nothing in `products/services.py`, `views.py`, or `api_views.py` mentions
Karnataka by name - it's all driven by the `State`/`District`/`City`/
`Locality` rows created in `seed_data.py`. See "How to add another state"
below for what that means in practice.

## Platform availability by location

`PlatformAvailability` is a simple, explainable tiering standing in for
real coverage data:
- **Bengaluru** (metro): all 5 platforms available.
- **Other major cities** (Mysuru, Mangaluru, Hubballi-Dharwad, Belagavi,
  Kalaburagi, Davanagere, Ballari, Shivamogga, Tumakuru, Udupi): Blinkit,
  Zepto, Swiggy Instamart.
- **Smaller towns**: Blinkit only.

This is itself simulated (see `seed_data.py` `TIER_*` constants) - real
platform coverage would come from each platform's actual serviceable-area
API/data, which this project has no access to. The mechanism (a
`PlatformAvailability` row per platform/locality, checked before any offer
is shown) is real; the specific tiers are a plausible stand-in.

**Display note**: every active platform is always listed for a product -
including ones that don't service the selected locality - so users can see
the full picture (e.g. "BigBasket: not available in this area") rather
than have platforms silently vanish. What's fail-closed is the *price*:
an unserviceable platform never gets a fabricated number, only a
"not available in this area" status. This is a deliberate two-part rule
(`OfferRow.serviceable` vs `OfferRow.is_available`) - see
`products/services.py` `compare_prices()`.

## Product images

Two-tier provider architecture (`products/image_providers.py`), both
caching to `Product.image_path` - templates only ever read that field,
never fetch anything at request time:

1. **`RemoteImageProvider`** - the intended real-photo path. Looks a
   product up on [Open Food Facts](https://world.openfoodfacts.org) (an
   open, crowd-sourced grocery database; data under ODbL, images under
   CC-BY-SA, and programmatic access is explicitly permitted with a clear
   User-Agent, which this provider sends) by brand + name, downloads the
   front-of-pack image if found, and caches it to
   `static/product_images/remote/<sku>.<ext>`. Every call has an explicit
   timeout and try/except - a failure (timeout, no match, bad response)
   returns `None`, never an exception or a broken image.
2. **`PlaceholderProvider`** - the guaranteed fallback. A deterministic
   SVG card (category-tinted background, brand-initial monogram, category
   name) via `products/imaging.py`. Never random/unrelated, never
   presented as a real photo.

**Honest limitation of this deployment**: this sandboxed build
environment's outbound network access is restricted to package
registries - it cannot reach `world.openfoodfacts.org` or any other
general image/API host. I verified this directly: running
`python manage.py fetch_product_images --limit 5` here produces a real
`403` from the egress proxy on every lookup, caught cleanly by the
provider's error handling, with **zero crashes and zero broken images** -
every product still gets its placeholder. So: **no, real images are not
populated in this build** - every product currently shows the SVG
placeholder. The code for real images is implemented, documented, and
ready to run wherever outbound network access exists; it just couldn't
be exercised end-to-end from here. This is stated plainly rather than
claimed as working.

Regardless of which provider supplies it, every image is served with
`loading="lazy"`, explicit `width`/`height` (prevents layout shift), and
`object-fit: contain` inside a fixed-aspect-ratio box - so a slow or
missing image never reflows the page or shows a broken-image icon.

### Seed data vs. image enrichment (kept separate on purpose)

`seed_data` calls `generate_product_images` (cheap, local, instant SVG
generation) automatically - but **never** `fetch_product_images` (makes
real network requests). Fetching real images is a deliberately separate,
opt-in, batched step:

```bash
python manage.py fetch_product_images --limit 200   # run again to process more
```

`--limit` bounds each run and already-fetched products are skipped, so
it's safe to run repeatedly/incrementally rather than trying to fetch
thousands of images synchronously at startup.

## Platform redirect ("Buy on ...") links

Every offer has no real per-product platform URL (all data is simulated -
see below), so every "Buy" button goes to the platform's real, live
website - either a verified search-results page for the product name, or,
where a working search-URL pattern couldn't be confirmed, the platform's
homepage. See `products/platform_links.py` for exactly which platforms
get which, and why:
- **Blinkit** (`blinkit.com/s/?q=`) and **Zepto**
  (`zeptonow.com/search?query=`): confirmed real search-URL patterns.
- **Flipkart Minutes**: uses Flipkart's general site search
  (`flipkart.com/search?q=`) - reliable, but not confirmed to deep-link
  into the Minutes quick-commerce section specifically.
- **Swiggy Instamart** and **BigBasket**: no publicly confirmed direct
  search-URL pattern (both are session/location-gated SPAs), so these
  fall back to the platform's real homepage rather than a guessed query
  string that might silently not work.

Every offer row also exposes `buy_link.is_search` so the UI never claims
a search page is an exact product page - the product detail page's note
says "opens Blinkit's real site with this product searched for you" only
when that's actually true, and something softer otherwise. Links open in
a new tab (`target="_blank" rel="noopener noreferrer"`).

## Responsive UI & accessibility

Rebuilt around explicit breakpoints (`static/css/styles.css`, "V5"
section) rather than one desktop layout shrunk down:
- **≤479px / 480-767px / 768-1023px / 1024-1279px / ≥1280px / ≥1440px**
  each get their own grid column counts and spacing - checked via
  `product-grid`/`deal-grid`/`stat-strip` column rules, not just a single
  generic `max-width` media query.
- **No page-wide horizontal scroll**: `html { overflow-x: hidden }` as a
  safety net, plus the actual fixes - the platform section uses an
  intentional `overflow-x: auto` carousel with scroll-snap (the *only*
  horizontally-scrolling element), and the comparison table converts to
  stacked cards below 640px (`data-label` + `::before` pattern) instead
  of forcing a 7-column table into a 320px viewport.
- **Location chip** truncates gracefully (`text-overflow: ellipsis`,
  capped width) instead of pushing the cart link off-screen with a long
  address, and shows "Locality / City / Change" instead of one run-on
  line.
- **Bottom mobile nav** (Home/Search/Categories/Cart), fixed with
  `env(safe-area-inset-bottom)` padding for notched phones, hidden
  ≥768px where the top nav suffices; page content gets bottom padding so
  nothing hides behind it.
- **Accessibility**: skip-to-content link, semantic `<header>`/`<main>`/
  `<footer>`/`<nav aria-label>`, table captions + `scope="col"` headers,
  visible `:focus-visible` outlines, `aria-label`s on icon-only controls
  (cart, location chip, per-offer "Buy" buttons), a associated `<label>`
  on the search input (visually hidden, not just a placeholder), and
  custom `404.html`/`500.html` so an error never shows a blank/broken
  page (verified via Django's test client with `DEBUG=False`, matching
  how these templates actually get used in production).

I did not have a real browser/device lab to pixel-test this in - the
above was built from sound CSS practice (flex/grid with `minmax`/
`auto-fit`, `box-sizing: border-box` throughout, no fixed pixel widths
wider than mobile viewports) and verified structurally (correct markup,
valid embedded JSON, correct availability data reaching the template),
not visually screenshot-diffed against the reference images.

## Demo vs. Live data

**Every price, availability, delivery estimate, and fee in this project is
simulated.** Quick-commerce platforms require a logged-in/located session
and are protected against automated scraping; scraping them without
authorization would violate their terms of service. This project does not
do that, and does not attempt to work around it (no CAPTCHA bypass, no
auth abuse, no rate-limit circumvention).

- `ProductOffer.is_demo` is `True` on every row in this project (kept as a
  real field, not just documentation, so a future live source wouldn't
  need a schema change).
- Every API response marks offers `"is_demo": true`.
- **Prices are simulated; the destination is not.** "Buy" buttons open
  each platform's real website (a real search page where confirmed, the
  real homepage otherwise - see "Platform redirect links" above) - the
  product page says so explicitly ("Prices shown are simulated...") so
  the price and the link are never conflated as both being live.
- `Platform.base_delivery_fee` / `free_delivery_above` are simulated and
  labelled as such (`"fee_is_simulated": true`) everywhere the basket
  optimizer surfaces them.

See `scrapers/mock_scraper.py` for the full explanation of how demo prices
are derived (deterministic per-product base price + category price band +
platform multiplier + locality cost index + small run-to-run noise).

## Dynamic pricing & price history

`ProductOffer.current_price` is always the *latest known* price, never the
only copy. Every price check:
1. Fetches a new observation from the platform's provider.
2. Updates `current_price`, `is_available`, `delivery_minutes`,
   `promotion_text`, and `last_checked_at` unconditionally.
3. Creates a new `PriceHistory` row **only if price or availability
   actually changed** (within a small rounding tolerance) since the last
   recorded observation. Deliberate choice: recording every check
   regardless of change would pad history with rows carrying no new
   information; recording only real changes keeps the chart and "recent
   average" meaningful, while `last_checked_at` still proves the data is
   fresh. See `products/pricing.py` `upsert_offer()`.

Running `python manage.py refresh_prices` repeatedly against the same
locality produces real drift — verified during development: a
`24 Mantra Urad Dal 500g` offer moved ₹58.00 → ₹57.89 → and its Instamart
price moved ₹60.33 → ₹62.79 across two consecutive runs, each creating a
new `PriceHistory` row.

### Price change UX
The product page shows `↓ ₹5 today` / `↑ ₹2 today` only when
`PriceHistory` actually has a previous observation to compare against
(`products/services.py` `compute_price_insights()`), never a guessed value.

## How price refresh works (lazy materialization)

With 2,500+ products, pre-generating every `(product, platform, locality)`
combination up front would mean hundreds of thousands of rows before a
single page loads — most of which would never be viewed. Instead:

- **Offers are materialized on demand.** The first time a product is
  compared in a locality (`compare_prices()` → `ensure_offers()`), the
  system prices it against every platform that services that locality
  (per `PlatformAvailability`) and caches the result as a `ProductOffer`.
  Existing offers are left alone.
- **`python manage.py refresh_prices`** re-checks offers that already
  exist — the "time has passed, prices may have moved" operation. Flags:
  `--locality "Koramangala"` to scope it, `--warm N` to pre-materialize N
  un-priced products (useful for demos/tests without browsing first).
- Search-result pages are paginated (24/page), which also bounds how many
  products get materialized per request — see "Performance."

This is why `seed_data` does **not** pre-generate offers: seeding 2,588
products is a few seconds; browsing naturally warms exactly what's viewed.

## How product ingestion works

`python manage.py import_products <file.json|file.csv> [--dry-run]` is
idempotent: running the same file twice produces `created=0` the second
time. Each record is:
1. **Validated** — name/brand/category/subcategory required; quantity+unit
   (or a `size` string like `"1kg"`) must parse to a known unit.
2. **Normalized** — `normalize_product_name()` lowercases, strips
   punctuation and embedded size tokens (`products/normalization.py`).
3. **Matched** against existing products by `(brand, normalized_name,
   quantity, unit)` — quantity and unit are **never fuzzy**, so
   `500ml != 1L` and `1kg != 5kg` always stay distinct products, even if
   their names are otherwise identical. This is deliberately conservative:
   under-matching (two records that are really the same product end up as
   two rows) is an easy fix; a false *positive* match silently corrupts
   price comparisons.
4. **Reported**: `created / updated / skipped / duplicate / invalid`
   counts, plus up to 10 example invalid-row reasons.

`--dry-run` wraps the whole import in a transaction and rolls it back —
nothing is written, including new `Category`/`Subcategory` rows.

## How to generate 2,000+ products

```bash
python manage.py generate_catalog --out fixtures/generated_products.json
python manage.py import_products fixtures/generated_products.json
```

`generate_catalog` expands `products/taxonomy.py`'s 62 templates (each a
brand × variant × size cross-product, e.g. `Lays × {Classic Salted, Masala
Munch, ...} × {52g, 90g, 150g}`) into individual records — **not** a
hand-written 2,000-line list. This currently yields **2,588** records; the
test suite asserts `expected_product_count() >= 2000`
(`products/tests/test_ingestion.py`).

`python manage.py seed_data [--products 2000]` runs both steps for you
(plus platforms, Karnataka geography, and platform availability), and is
safe to re-run — it skips regeneration if the catalog already meets the
target.

## Comparison & Best-Deal engine

`compare_prices(product, locality)`:
1. Only platforms with an `available` `PlatformAvailability` row for that
   locality are considered at all.
2. Offers are materialized on demand (see above).
3. Unavailable offers are excluded from "best price" but still shown
   (visually muted).
4. Rows are sorted by price; `savings_vs_next_best` = 2nd-cheapest minus
   cheapest.

## How basket splitting works

`compare_basket(items, locality)`:
1. **Single-platform totals**: for each platform, only counted if it can
   supply *every* item in the basket; subtotal + simulated delivery fee
   (waived above `Platform.free_delivery_above`, else `base_delivery_fee`).
2. **Optimized split**: cheapest available platform per item,
   independently, grouped into per-platform sub-orders (each incurring its
   own simulated delivery fee).
3. **Recommendation**: the split is only recommended
   (`recommend_split=True`) if it beats the best single-platform total by
   at least `MIN_SPLIT_SAVINGS` (₹15) — verified during development: with
   near-identical prices, splitting was correctly declined because two
   delivery fees outweighed the product-price savings.
4. **Explanation**: per-item price gaps (`"₹18 cheaper on milk on
   Zepto"`), computed from the same numbers shown in the table — never a
   black-box score.

## Search

`Product.objects.filter(Q(name__icontains=...) | Q(brand__icontains=...) |
Q(subcategory__name__icontains=...) | Q(subcategory__category__name__icontains=...))`,
backed by indexes on all four fields, paginated at the DB level (Django
`Paginator` / DRF `PageNumberPagination`) — never a Python-side filter over
the full catalog.

## Performance

- `select_related("subcategory__category")`, `("platform")`,
  `("city__district__state")` throughout — no N+1 queries on the hot
  paths (verified: home page renders 24 products × 5 platforms in well
  under a second on SQLite in this sandbox).
- Search results and the basket are paginated/bounded, which also bounds
  lazy offer materialization per request.
- Light caching added where it's cheap and clearly correct: the Karnataka
  location tree (`products/context_processors.py`) is cached for an hour
  since geography barely changes - not a general-purpose cache layer.
- No Celery/Redis — not justified yet at this scale (2,500 products, tens
  of localities). See "Future Improvements."

## Scaling to 3 crore+ (30M+) products

The catalog capacity claim is architectural, not populated data - **this
build seeds 2,588 real products, not 30 million**, and nothing in the UI
or API states otherwise. What's actually in place to support that scale:

- **Schema**: `Product` is already indexed on `name`/`brand`/
  `normalized_name`/`subcategory`, with the dedup constraint
  doubling as a lookup index - no schema change needed to grow the row
  count.
- **Ingestion**: `import_products` now supports `--batch-size` (commits
  every N records instead of one all-or-nothing transaction - a 30M-row
  single transaction would hold locks and memory far too long) and
  `--offset`/`--limit` (process a huge file across multiple resumable
  runs). Verified: importing 5 records with `--batch-size 2` still
  produces all 5, in 3 separate commits.
- **Pricing**: lazy materialization (see below) means offer rows only
  ever get created for products someone actually views - the pricing
  table never needs to hold `30M × 5 platforms × N localities` rows.
- **Pagination**: already in place everywhere (Django `Paginator` for the
  UI, DRF `PageNumberPagination` for the API) - never a full-table load.

**What would still need to change at true 30M+ scale** (documented
honestly rather than silently glossed over):
- `icontains` search (`LIKE '%term%'`) doesn't use a B-tree index and
  degrades badly past a few million rows on SQLite/MySQL. At real scale
  this needs Postgres `pg_trgm`/`GIN` indexes, SQLite FTS5, or a
  dedicated search engine (Meilisearch/Elasticsearch/Algolia) - not
  implemented here, since it would be premature for a 2,588-row catalog.
- `Paginator.count` runs a `COUNT(*)` per page load, which gets expensive
  on a 30M-row table without an estimate (e.g. Postgres
  `pg_class.reltuples`) or switching to DRF's `CursorPagination` (no
  total count, keyset-based) for the product API specifically.
- MySQL/Postgres in production, not SQLite - SQLite is explicitly a local
  -dev convenience here (see "Database / SQLite" below), never proposed
  as the production store at this scale.

None of this is Karnataka-specific or otherwise hard-coded - see "How to
add another state" for why the geography and business logic already
scale independently of the catalog size.

## API

All list endpoints paginated (`?page=`).

| Endpoint | Purpose |
|---|---|
| `GET /api/products/?search=&locality=&category=` | Search, with per-product best price/platform if `locality` given. |
| `GET /api/products/<id>/` | Product details. |
| `GET /api/products/<id>/compare/?locality=` | Full platform comparison (locality required). |
| `GET /api/products/<id>/history/?locality=` | Price history + computed insights. |
| `GET /api/platforms/` | All platforms (incl. simulated fee data). |
| `GET /api/localities/?q=` | Locality/city/pincode search - powers the location picker. |
| `POST /api/basket/compare/` | `{"locality_id": 5, "items": [{"product_id": 1, "quantity": 2}]}` → single-platform totals, optimized split, savings, explanation. |

## How to add a new platform
1. Subclass `BaseScraper` in a new `scrapers/<name>.py` (see `blinkit.py`).
2. Add it to `SCRAPER_REGISTRY` in `scrapers/registry.py`.
3. Create a `Platform` row (admin, or extend `seed_data.py`'s
   `PLATFORM_SEED`) and `PlatformAvailability` rows for where it operates.

Nothing in `products/services.py`, `views.py`, or `api_views.py` changes.

## How to add another state
Karnataka is data, not business logic. To add e.g. Tamil Nadu:
1. Create a `State` row, `District`/`City`/`Locality` rows under it.
2. Add `PlatformAvailability` rows for whichever platforms serve those
   localities.
3. That's it — `compare_prices`, `compare_basket`, search, and the API
   all operate on whatever `Locality` they're given.

The only Karnataka-specific code is the seed data in
`products/management/commands/seed_data.py` (`DISTRICT_CITY_MAP`,
`LOCALITY_MAP`, `TIER_*`) — everything under `products/services.py`,
`pricing.py`, `views.py`, and `api_views.py` is geography-agnostic.

## Installation

```bash
git clone <repository-url>
cd quick-commerce-price-comparator
python -m venv venv
source venv/bin/activate   # venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
```

### Local development — SQLite (no MySQL required)
```env
# in .env
DB_ENGINE=sqlite
```
```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_data
python manage.py runserver
```
Visit `http://127.0.0.1:8000/` for the app, `/admin/` for the admin,
`/api/products/` for the API root.

### Production / deployment — MySQL
Set `DB_ENGINE=mysql` (or omit it — it's the default) and fill in
`DB_NAME`/`DB_USER`/`DB_PASSWORD`/`DB_HOST`/`DB_PORT` in `.env`. Same
`migrate`/`seed_data` commands. Only the `DATABASE` setting in
`config/settings.py` changes between the two.

## Running tests

```bash
python manage.py test
```

88 tests: geography/taxonomy models and constraints, normalization/dedup
utilities, idempotent ingestion, catalog generation (count + realism
checks), the lazy-materialization pricing layer (including fail-closed
availability), comparison + price-insight logic, basket optimization
(single-platform totals, split recommendation threshold, explanation),
all API endpoints, and the provider/adapter layer.

## Verified before delivery

- `python manage.py check` / `migrate` — clean, additive migrations only
  (`0002_product_image_path` on top of the existing `0001`) — no prior
  data touched.
- `python manage.py test` — 102/102 passing, confirmed across 5
  consecutive runs.
- `python manage.py seed_data` — 2,588 products (each with a generated
  placeholder image), 28 cities/49 localities across 26 Karnataka
  districts, 245 `(platform, locality)` availability rows.
- Manual verification via `curl`: homepage, Bread/Milk/Maggi/Lays search,
  product detail, cart add → basket compare, `/api/` endpoints, admin.
- Confirmed the platform section reads real data: in Gadag (tier 3), the
  homepage's platform cards show Blinkit "Delivers here" and the other 4
  "Not available here" - pulled directly from `PlatformAvailability`, not
  hard-coded.
- Confirmed the location tree embedded for the "Browse" picker tab is
  valid JSON: 26 districts, 49 localities, ~4.4KB.
- Confirmed responsive markup lands correctly: the comparison table's
  `data-label` attributes are present on the detail page (30, matching 5
  platforms × 6 labeled columns) and on the cart page once it actually
  has an item (16, confirmed via a real add-to-cart request - an empty
  cart correctly shows an empty state instead, not a bug).
- Confirmed `fetch_product_images` fails closed in this sandbox (see
  "Product images") - real `403`s from the egress proxy, caught cleanly,
  zero crashes, every product keeps its placeholder.
- Confirmed `404.html`/`500.html` actually render through Django's real
  error-handling path (`DEBUG=False` + Django's test client for 404;
  `render_to_string` for the intentionally-standalone 500 page) rather
  than just eyeballing the template source.
- Batch/resumable import verified: `--batch-size 2` on 5 records still
  produces `created=5` (across 3 commits); `--offset`/`--limit` produces
  the same end state as one unsplit run.

## Limitations

- No real platform integrations — everything is simulated, by design (see
  "Demo vs. Live data"). No CAPTCHA bypass or scraping-protection evasion
  was attempted or is planned.
- **Product images are placeholders in this build, not real photography.**
  The real-image path (`RemoteImageProvider`, Open Food Facts) is
  implemented and documented but unverifiable from this sandbox, which
  has no outbound route to it — see "Product images" for the concrete
  test that proves the fallback, not the fetch, is what's actually
  running.
- **The 3-crore catalog figure is architectural capacity, not populated
  data.** This build seeds 2,588 real products. See "Scaling to 3 crore+"
  for exactly what's in place vs. what would still need to change (real
  full-text search infra, cursor pagination, Postgres/MySQL) to actually
  reach that scale.
- Instamart and BigBasket "Buy" links go to the platform homepage, not a
  search page, because no working search-URL pattern for either could be
  confirmed — see "Platform redirect links."
- Karnataka coverage is representative (28 cities, 49 localities), not
  exhaustive — most cities outside Bengaluru have 1-2 localities, and most
  pincodes are left blank rather than guessed.
- No user accounts — cart and location live in the session (see "Why no
  authentication" below); a price-alert feature would be the natural
  reason to add one.
- Delivery fees/min-order-values are simulated per platform (flat values),
  not modeled per product weight/distance.
- Responsive layout was built from CSS best practice and verified
  structurally (correct markup, no fixed-width overflow sources), not
  visually screenshot-diffed against a real device/browser lab — see
  "Responsive UI & accessibility" for exactly what that does and doesn't
  cover.
- The basket optimizer treats each item independently when building the
  split; it doesn't search for combinations beyond "cheapest per item,"
  which is sufficient for the explanation to stay simple/auditable but
  wouldn't capture, e.g., quantity-discount thresholds if those existed.

## Why no authentication
The core product — "search a product, see the best price near me, compare
my basket" — needs no account, and both location and cart live in the
session. Adding login/signup now would be friction without payoff. A
price-alert feature (mentioned in "Future Improvements") is the natural
point where accounts would earn their place.

## Future Improvements
- Real, authorized platform integrations where technically and legally
  appropriate, slotted in via the existing adapter pattern.
- Celery + beat for scheduled `refresh_prices` runs instead of manual/CLI.
- Redis caching for hot product/locality comparisons if traffic grew.
- Price-drop alerts (would justify adding accounts).
- Automatic location detection (current manual picker stays as fallback).
- Expansion to more states (Tamil Nadu, Maharashtra, etc. — see "How to
  add another state").
- A combinatorial basket optimizer (beyond per-item-cheapest) if
  quantity-based discounts or platform-specific coupons are ever modeled.
