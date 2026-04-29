# InvTrendDB

https://invtrend-db.streamlit.app/

An interactive inventory analytics dashboard with anomaly detection.

## Features
- **Data Cleaning**: Automatically handles missing values, parses dates, and normalizes column names.
- **Trend Visualizations**: View weekly throughput, delay frequency, top items, and status breakdowns via clean Plotly charts.
- **Anomaly Flagging**: Automatically highlights rows where quantity or delay days are statistically out of range using Z-score detection (configurable sigma).
- **Summary Stats**: View total shipments, average delay, anomaly count, and date ranges at a glance.

## Installation

1. Create a virtual environment:
   ```bash
   python -m venv venv
   ```
2. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - Mac/Linux: `source venv/bin/activate`
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the Streamlit application:
```bash
streamlit run app.py
```

You can upload your own inventory/shipment CSV data or use the provided `sample_data.csv` for a demonstration.

## Dataset Structure
The app automatically detects relevant columns, but works best with a CSV containing:
- `date` or `timestamp`
- `item`, `product`, or `sku`
- `quantity` or `amount`
- `delay` or `lead_time`
- `status`
