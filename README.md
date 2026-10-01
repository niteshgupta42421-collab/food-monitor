# 🍽️ FoodWaste360

**Measure. Understand. Reduce.**

FoodWaste360 is a smart food-waste management and environmental impact
intelligence system for hotels, restaurants, cafeterias, hostels, messes and
other large-scale food service operations.

It answers one question end to end:

> How much food is being wasted, where is it being wasted, what resources are
> associated with that waste, what is the estimated financial/environmental
> impact, and what operational changes could reduce future waste?

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

The app opens in your browser. The database, default food factors and demo
user accounts are created automatically on first run.

### Demo accounts

All demo accounts share the password **`demo1234`** (they are demonstration
accounts only — change or remove them for production use):

| Role | Email |
| --- | --- |
| Administrator | `admin@foodwaste360.demo` |
| Hotel / Restaurant Manager | `manager@foodwaste360.demo` |
| Kitchen Manager / Chef | `kitchen@foodwaste360.demo` |
| Staff | `staff@foodwaste360.demo` |

The login screen has one-click buttons for these accounts.

### Demo data

Open the **Dashboard** and press **Load Demo Hotel** (or use Settings →
Data management). This creates a deterministic 30-day hotel scenario:

* 8,000 kg food prepared per day
* 1,000 kg recorded waste: 250 kg kitchen + 150 kg serving + 600 kg plate
* 12.50% waste rate, 2,000 customers per day

---

## Pages

| Page | Purpose |
| --- | --- |
| **Dashboard** | Cards + charts for the selected reporting period |
| **Production** | Prepared / served / consumed per food per day |
| **Waste Tracking** | Kitchen and serving waste entries with reasons and warnings |
| **Plate Waste** | Plate-waste analysis (customers, g/customer) + plate-washing water calculator |
| **Food Database** | Food items, costs and documented impact factors (admin editing) |
| **Impact Calculator** | Estimated value lost, CO₂e, food water footprint + Methodology & Sources |
| **Analytics** | Historical trends with Plotly charts and CSV export |
| **What-If Simulator** | Scenario estimates (production, serving size, customers, target rate) |
| **Smart Recommendations** | Waste Detective observations + data-based recommendations |
| **Reports** | Period report with CSV export (PDF marked as future work) |
| **Settings** | Demo data, clearing records, user management (admin only) |

Reporting period presets (Today / Yesterday / Last 7 days / Last 30 days /
Custom) live in the sidebar and apply to every analytics page.

---

## Data types used throughout the app

| Label | Meaning |
| --- | --- |
| **Measured** | Entered by your team (production, waste, customers) |
| **Calculated** | Derived mathematically from measured data (waste %, averages) |
| **Estimated** | Measured waste × a documented external factor (₹, CO₂e, water) |
| **Simulated** | What-if scenario results — never guaranteed savings |

Estimates are never presented as exact measurements.

## Environmental factor sources

No environmental factor is invented in this app. Factors come from:

* **Poore, J., & Nemecek, T. (2018).** *Reducing food's environmental impacts
  through producers and consumers.* Science, 360(6392), 987-992 — global-mean
  values processed by Our World in Data:
  * [GHG per kg of food product](https://ourworldindata.org/grapher/ghg-per-kg-poore)
  * [Freshwater withdrawals per kg](https://ourworldindata.org/grapher/water-withdrawals-per-kg-poore)

Every factor is stored per food with its value, unit, source, reference and
date (see `data/food_factors.csv` and the Food Database page). Prepared dishes
without a dedicated study use the closest documented commodity factor as a
clearly labelled **proxy** (e.g. roti → wheat & rye); idli/dosa use a
calculated rice + pulses composite with the ratio documented. Administrators
can edit any factor, and a source is always required.

**Plate-washing water** is a separate estimate computed from your own inputs
(flow rate × time × plates, bucket size × buckets, dishwasher litres × cycles,
or a directly entered total). It is never combined with the food water
footprint.

## Project structure

```
app.py                  # Entry point: config, login, sidebar, navigation
streamlit_app.py        # Streamlit Community Cloud entry (runs app.py)
database/
    database.py         # Data access layer (all queries parameterized)
    schema.py           # SQLite schema, password hashing, seeding
    demo_data.py        # Deterministic 30-day demo dataset generator
pages/                  # One module per page (see table above)
services/
    calculations.py     # Totals, per-food tables, daily aggregates
    impact_engine.py    # CO₂e / water / financial estimates + methodology
    recommendation_engine.py  # Waste Detective + Smart Recommendations
    simulator.py        # What-If scenarios (all labelled simulated)
data/
    food_factors.csv    # Default foods with documented factors + sources
utils/
    validation.py       # Friendly input validation rules
    formatting.py       # kg / ₹ / litres / % formatting (standard grouping)
    ui.py               # Cards, chips, CSS, date-range selector
    charts.py           # Shared Plotly chart builders
```

## Security & data notes

* All SQL is parameterized; user input is validated with friendly messages.
* Passwords are stored as salted PBKDF2-SHA256 hashes — never in plain text.
* No API keys exist in version 1 and none are stored in the code. If an
  external AI/API service is added later, its key must come from an
  environment variable (see `.env.example`), never from source code.
* Only a name, email and role are collected per user.

## Limitations & future work

* Environmental factors are global averages — not supplier-specific values.
* Financial values depend on the cost per kg your organization maintains.
* PDF export is marked as a disabled placeholder on the Reports page.
* ML forecasting and external AI services are intentionally **not** included
  in this version; the modular `services/` layer is ready for them.
