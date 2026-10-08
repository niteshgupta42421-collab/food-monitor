# 🍽️ MealFlow360

**Sell Smart. Cook Right. Waste Less.**

MealFlow360 is a food sales, kitchen production, inventory flow and waste
intelligence system for restaurants, hotels, cafeterias, hostels, messes and
other large-scale food service operations.

It connects what you **sell** to what you **cook** and what you **throw away**,
and answers one question end to end:

> How much food did we sell, how much is left, how much was wasted, what is the
> estimated financial and environmental impact, and how much should we cook
> next?

---

## Quick start

```powershell
# 1. (Recommended) create a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
streamlit run app.py
```

The app opens in your browser. The database, default food master data and demo
user accounts are created automatically on first run.

### Demo accounts

| Account | Email | Password |
| --- | --- | --- |
| **Flagship demo (Administrator)** | `demo@mealflow360.com` | `Demo@123` |
| Administrator | `admin@mealflow360.demo` | `demo1234` |
| Restaurant Manager | `manager@mealflow360.demo` | `demo1234` |
| Kitchen Manager / Chef | `kitchen@mealflow360.demo` | `demo1234` |
| Staff | `staff@mealflow360.demo` | `demo1234` |

The login screen has one-click buttons for every account. New users can also
**create an account** (the registering user becomes the administrator) and
**reset a forgotten password** — in this offline demo the reset is verified
against the registered name and email instead of an email link.

### Demo data — The Urban Thali

Press **🍛 Load The Urban Thali demo** on the Dashboard (or in Settings →
Data management). This creates a deterministic 30-day dataset for a
~520-cover Indian restaurant with 8 dishes:

| Dish | Prepared | Sold | Story on the last day |
| --- | --- | --- | --- |
| Rice | 180 plates | 177 plates | Near sell-out → 🟡 Low |
| Dal | 160 bowls | 155 bowls | Healthy stock → 🟢 |
| Chapati | 320 pieces | 320 pieces | Sold out → 🔴 Out |
| Biryani | 95 plates | 38 plates | Overstock — 12 kg planned carry-over |
| Paneer | 75 plates | 74 plates | Near sell-out → 🟡 Low |
| Bhaji | 140 portions | 134 portions | Healthy stock → 🟢 |
| Curd | 110 bowls | 104 bowls | 0.5 kg planned carry-over |
| Dosa | 120 plates | 120 plates | Made to order |

Roughly 193 kg prepared and 13.4 kg wasted per day (kitchen 2.0 + serving 2.3
+ plate 9.1 ≈ 6.9%). The generator uses a fixed random seed, so every machine
gets the same story, and the final day always matches this table.

---

## Pages

| Page | Purpose |
| --- | --- |
| **Dashboard** | Revenue, food sold, remaining stock, waste + charts for the period |
| **Sales** | Record sales entries (dine-in / takeaway / delivery / buffet) with kg conversion and revenue |
| **Plate Waste** | Plate-waste analysis (customers, g/customer) + plate-washing water calculator |
| **Kitchen Control Center** | "What to cook next?" replenishment planner + live stock alerts |
| **Production** | Food prepared entry per food/day — served & consumed derived |
| **Inventory** | Remaining food per dish with 🟢🟡🔴 status and carry-over planning |
| **Waste Tracking** | Kitchen and serving waste entries with reasons and warnings |
| **Impact Calculator** | Estimated value lost, CO₂e, food water footprint + Methodology & Sources |
| **Analytics** | Historical trends with Plotly charts and CSV export |
| **Smart Forecast** | Simple historical demand forecast (clearly labelled Estimated) |
| **What-If Simulator** | Scenario estimates (production, serving size, customers, target rate) |
| **Smart Recommendations** | Waste Detective observations + data-based recommendations |
| **Reports** | Period report with CSV export (PDF marked as future work) |
| **Food Master** | Food items, prices, portion sizes, thresholds, modes and impact factors |
| **Settings** | Profile & appearance (light/dark/warm theme), demo data, users (admin) |

Reporting period presets (Today / Yesterday / Last 7 days / Last 30 days /
Custom) live in the sidebar and apply to every analytics page. The sidebar
also shows your restaurant name and a **Log out** button.

---

## How sales, stock and waste connect

```text
AVAILABLE FOR SERVICE = prepared - kitchen waste
REMAINING = available - sold            (sales × portion size → kilograms)
CARRY-OVER = planned on the Inventory page (NOT waste)
WASTE = kitchen + serving + plate       (each kilogram counted once)
```

* **Sales → kilograms.** Every food has a portion size (e.g. 250 g per plate),
  so 180 plates × 250 g = 45 kg sold. Set it once in the Food Master page.
* **Remaining food** is always derived (available − sold), never stored.
* **Carry-over is not waste.** Food planned for the next service is stored as
  a carry-over row and excluded from waste totals deliberately.
* **Low-stock thresholds** per food turn the Inventory page 🟡; nothing left
  means 🔴; a healthy remainder is 🟢.
* **"What to cook next?"** recommends
  `max(expected demand − available, 0)` per dish, using the kitchen's own
  demand plan when entered, otherwise a clearly labelled forecast.
* **Made-to-order dishes** (e.g. Dosa) are excluded from replenishment
  recommendations — you cook them on demand, not in advance.

## Data types used throughout the app

| Label | Meaning |
| --- | --- |
| **Measured** | Entered by your team (prepared food, sales, waste, customers) |
| **Calculated** | Derived mathematically (available / served / consumed, remaining, waste %, sell-through) |
| **Estimated** | Measured waste × a documented external factor (₹, CO₂e, water) or a labelled forecast |
| **Simulated** | What-if scenario results — never guaranteed savings |

Estimates are never presented as exact measurements.

### Production & waste accounting model

One model defines every food quantity in the app (`services/accounting.py`):

```text
FOOD PREPARED
      |
      +----> KITCHEN WASTE
      v
AVAILABLE FOR SERVICE = prepared - kitchen waste
      |
      +----> SERVING WASTE
      v
FOOD SERVED = available for service - serving waste
      |
      +----> PLATE WASTE
      v
FOOD CONSUMED = served - plate waste
```

* Prepared, kitchen waste, serving waste, plate waste and sales are
  **measured** inputs; available for service, served, consumed and remaining
  are **calculated**.
* Total waste = kitchen + serving + plate — each kilogram is counted once.
  Sales and carry-over are never part of the waste total.
* Waste percentage = total waste ÷ prepared × 100.
* The served/consumed values stored in the database are save-time snapshots.
  Every page re-derives the displayed quantities from prepared + waste +
  sales records, so food is never double-counted.

## Environmental factor sources

No environmental factor is invented in this app. Factors come from:

* **Poore, J., & Nemecek, T. (2018).** *Reducing food's environmental impacts
  through producers and consumers.* Science, 360(6392), 987-992 — global-mean
  values processed by Our World in Data:
  * [GHG per kg of food product](https://ourworldindata.org/grapher/ghg-per-kg-poore)
  * [Freshwater withdrawals per kg](https://ourworldindata.org/grapher/water-withdrawals-per-kg-poore)

Every factor is stored per food with its value, unit, source, reference and
date (see `data/food_factors.csv` and the Food Master page). Prepared dishes
without a dedicated study use the closest documented commodity factor as a
clearly labelled **proxy** (e.g. roti → wheat & rye). Administrators can edit
any factor, and a source is always required.

**Plate-washing water** is a separate estimate computed from your own inputs
(flow rate × time × plates, bucket size × buckets, dishwasher litres × cycles,
or a directly entered total). It is never combined with the food water
footprint.

## Project structure

```
app.py                  # Entry point: config, theme, auth, sidebar, navigation
streamlit_app.py        # Streamlit Community Cloud entry (runs app.py)
database/
    database.py         # Data access layer (all queries parameterized)
    schema.py           # SQLite schema, migrations, password hashing, seeding
    demo_data.py        # The Urban Thali deterministic demo generator
pages/                  # One module per page (see table above)
services/
    accounting.py       # THE food accounting model (single definitions)
    finance.py          # Sales → revenue / kg / profit metrics
    forecasting.py      # Simple historical demand forecast (labelled Estimated)
    stock.py            # Per-food daily stock state and 🟢🟡🔴 status
    calculations.py     # Totals, per-food tables, daily aggregates
    impact_engine.py    # CO₂e / water / financial estimates + methodology
    recommendation_engine.py  # Waste Detective + Smart Recommendations
    simulator.py        # What-If scenarios (all labelled simulated)
data/
    food_factors.csv    # Default foods with prices, portions and factors
utils/
    theme.py            # Light / dark / warm themes (CSS variables)
    validation.py       # Friendly input validation rules
    formatting.py       # kg / ₹ / litres / % formatting (standard grouping)
    ui.py               # Cards, chips, CSS, date-range selector
    charts.py           # Shared Plotly chart builders
```

## Security & data notes

* All SQL is parameterized; user input is validated with friendly messages.
* Passwords are stored as salted PBKDF2-SHA256 hashes — never in plain text.
* Each user has a role (admin / manager / kitchen / staff) that controls which
  pages they can see; the sidebar only shows permitted pages.
* Themes and profile details are stored per user in the local SQLite database.
* No API keys exist in this version and none are stored in the code. If an
  external AI/API service is added later, its key must come from an
  environment variable (see `.env.example`), never from source code.
* Only a name, email, role, restaurant name and theme preference are collected
  per user.

## Limitations & future work

* Environmental factors are global averages — not supplier-specific values.
* Financial values depend on the cost and selling prices your organization
  maintains in the Food Master page.
* The Smart Forecast is a transparent historical average (recent days blended
  with the same weekday) — not machine learning; every value is labelled
  Estimated.
* Password reset works against the registered name because no email service is
  configured (offline demo).
* PDF export is marked as a disabled placeholder on the Reports page.
* ML forecasting and external AI services are intentionally **not** included
  in this version; the modular `services/` layer is ready for them.
