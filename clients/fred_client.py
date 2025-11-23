"""
FRED (Federal Reserve Economic Data) Client
Access 500,000+ economic time series from the St. Louis Federal Reserve
"""

import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import time


class FREDClient:
    """Complete FRED API Client for Economic Data"""

    def __init__(self, api_key: str, rate_limit_delay: float = 0.1):
        """
        Initialize FRED client

        Args:
            api_key: Your FRED API key from https://fred.stlouisfed.org/docs/api/api_key.html
            rate_limit_delay: Delay between requests (seconds)
        """
        self.api_key = api_key
        self.base_url = "https://api.stlouisfed.org/fred"
        self.rate_limit_delay = rate_limit_delay
        self._last_request_time = 0

    def _request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make API request with rate limiting"""
        # Rate limiting
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)

        if params is None:
            params = {}
        params['api_key'] = self.api_key
        params['file_type'] = 'json'

        url = f"{self.base_url}/{endpoint}"
        response = requests.get(url, params=params, timeout=15)
        self._last_request_time = time.time()

        response.raise_for_status()
        return response.json()

    # =========================================================================
    # SERIES - GET ECONOMIC DATA
    # =========================================================================

    def get_series(self, series_id: str, observation_start: Optional[str] = None,
                   observation_end: Optional[str] = None, limit: int = 100000,
                   sort_order: str = "asc") -> Dict:
        """
        Get observations (data points) for an economic data series

        Args:
            series_id: FRED series ID (e.g., 'GDP', 'UNRATE', 'DFF')
            observation_start: Start date (YYYY-MM-DD)
            observation_end: End date (YYYY-MM-DD)
            limit: Maximum number of results
            sort_order: Sort order (asc, desc)

        Returns:
            Dict with observations
        """
        params = {"series_id": series_id, "limit": limit, "sort_order": sort_order}
        if observation_start:
            params["observation_start"] = observation_start
        if observation_end:
            params["observation_end"] = observation_end

        return self._request("series/observations", params)

    def get_series_info(self, series_id: str) -> Dict:
        """
        Get information about a series

        Args:
            series_id: FRED series ID

        Returns:
            Dict with series metadata (title, units, frequency, etc.)
        """
        params = {"series_id": series_id}
        return self._request("series", params)

    def search_series(self, search_text: str, limit: int = 100,
                     order_by: str = "search_rank") -> Dict:
        """
        Search for series by text

        Args:
            search_text: Keywords to search for
            limit: Maximum results
            order_by: Order results by (search_rank, series_id, title, units, frequency, etc.)

        Returns:
            Dict with matching series
        """
        params = {"search_text": search_text, "limit": limit, "order_by": order_by}
        return self._request("series/search", params)

    def get_series_categories(self, series_id: str) -> Dict:
        """Get categories for a series"""
        params = {"series_id": series_id}
        return self._request("series/categories", params)

    def get_series_tags(self, series_id: str) -> Dict:
        """Get tags for a series"""
        params = {"series_id": series_id}
        return self._request("series/tags", params)

    # =========================================================================
    # CATEGORIES - BROWSE DATA BY CATEGORY
    # =========================================================================

    def get_category(self, category_id: int = 0) -> Dict:
        """
        Get a category

        Args:
            category_id: Category ID (0 = root category)

        Returns:
            Dict with category info
        """
        params = {"category_id": category_id}
        return self._request("category", params)

    def get_category_children(self, category_id: int = 0) -> Dict:
        """Get child categories"""
        params = {"category_id": category_id}
        return self._request("category/children", params)

    def get_category_series(self, category_id: int, limit: int = 1000) -> Dict:
        """Get all series in a category"""
        params = {"category_id": category_id, "limit": limit}
        return self._request("category/series", params)

    # =========================================================================
    # RELEASES - DATA RELEASES
    # =========================================================================

    def get_releases(self, limit: int = 1000) -> Dict:
        """Get all releases of economic data"""
        params = {"limit": limit}
        return self._request("releases", params)

    def get_release(self, release_id: int) -> Dict:
        """Get a specific release"""
        params = {"release_id": release_id}
        return self._request("release", params)

    def get_release_series(self, release_id: int, limit: int = 1000) -> Dict:
        """Get series in a release"""
        params = {"release_id": release_id, "limit": limit}
        return self._request("release/series", params)

    def get_release_dates(self, release_id: int, limit: int = 10000) -> Dict:
        """Get release dates"""
        params = {"release_id": release_id, "limit": limit}
        return self._request("release/dates", params)

    # =========================================================================
    # TAGS - SEARCH BY TAGS
    # =========================================================================

    def get_tags(self, limit: int = 1000, order_by: str = "series_count") -> Dict:
        """Get all tags"""
        params = {"limit": limit, "order_by": order_by}
        return self._request("tags", params)

    def search_tags(self, tag_names: str, limit: int = 1000) -> Dict:
        """
        Search for tags

        Args:
            tag_names: Semicolon delimited list of tag names (e.g., 'gdp;usa')
        """
        params = {"tag_names": tag_names, "limit": limit}
        return self._request("tags/series", params)

    # =========================================================================
    # HELPER METHODS - COMMON ECONOMIC INDICATORS
    # =========================================================================

    def get_gdp(self, years: int = 10) -> Dict:
        """Get US GDP data"""
        start = (datetime.now() - timedelta(days=years*365)).strftime("%Y-%m-%d")
        return self.get_series("GDP", observation_start=start)

    def get_unemployment_rate(self, years: int = 10) -> Dict:
        """Get US unemployment rate"""
        start = (datetime.now() - timedelta(days=years*365)).strftime("%Y-%m-%d")
        return self.get_series("UNRATE", observation_start=start)

    def get_inflation_cpi(self, years: int = 10) -> Dict:
        """Get CPI (Consumer Price Index) - inflation measure"""
        start = (datetime.now() - timedelta(days=years*365)).strftime("%Y-%m-%d")
        return self.get_series("CPIAUCSL", observation_start=start)

    def get_fed_funds_rate(self, years: int = 10) -> Dict:
        """Get Federal Funds Rate"""
        start = (datetime.now() - timedelta(days=years*365)).strftime("%Y-%m-%d")
        return self.get_series("DFF", observation_start=start)

    def get_10year_treasury(self, years: int = 10) -> Dict:
        """Get 10-Year Treasury Yield"""
        start = (datetime.now() - timedelta(days=years*365)).strftime("%Y-%m-%d")
        return self.get_series("DGS10", observation_start=start)

    def get_sp500(self, years: int = 10) -> Dict:
        """Get S&P 500 index"""
        start = (datetime.now() - timedelta(days=years*365)).strftime("%Y-%m-%d")
        return self.get_series("SP500", observation_start=start)

    def get_consumer_sentiment(self, years: int = 10) -> Dict:
        """Get Consumer Sentiment Index"""
        start = (datetime.now() - timedelta(days=years*365)).strftime("%Y-%m-%d")
        return self.get_series("UMCSENT", observation_start=start)

    def get_retail_sales(self, years: int = 10) -> Dict:
        """Get Retail Sales"""
        start = (datetime.now() - timedelta(days=years*365)).strftime("%Y-%m-%d")
        return self.get_series("RSXFS", observation_start=start)

    def get_housing_starts(self, years: int = 10) -> Dict:
        """Get Housing Starts"""
        start = (datetime.now() - timedelta(days=years*365)).strftime("%Y-%m-%d")
        return self.get_series("HOUST", observation_start=start)

    def get_industrial_production(self, years: int = 10) -> Dict:
        """Get Industrial Production Index"""
        start = (datetime.now() - timedelta(days=years*365)).strftime("%Y-%m-%d")
        return self.get_series("INDPRO", observation_start=start)

    def get_pce_inflation(self, years: int = 10) -> Dict:
        """Get PCE (Personal Consumption Expenditures) - Fed's preferred inflation measure"""
        start = (datetime.now() - timedelta(days=years*365)).strftime("%Y-%m-%d")
        return self.get_series("PCEPI", observation_start=start)

    def get_m2_money_supply(self, years: int = 10) -> Dict:
        """Get M2 Money Supply"""
        start = (datetime.now() - timedelta(days=years*365)).strftime("%Y-%m-%d")
        return self.get_series("M2SL", observation_start=start)

    def get_vix(self, years: int = 10) -> Dict:
        """Get VIX (Volatility Index)"""
        start = (datetime.now() - timedelta(days=years*365)).strftime("%Y-%m-%d")
        return self.get_series("VIXCLS", observation_start=start)

    def get_employment(self, years: int = 10) -> Dict:
        """Get Total Nonfarm Payrolls"""
        start = (datetime.now() - timedelta(days=years*365)).strftime("%Y-%m-%d")
        return self.get_series("PAYEMS", observation_start=start)

    def get_real_gdp(self, years: int = 10) -> Dict:
        """Get Real GDP (inflation-adjusted)"""
        start = (datetime.now() - timedelta(days=years*365)).strftime("%Y-%m-%d")
        return self.get_series("GDPC1", observation_start=start)

    # =========================================================================
    # INTERNATIONAL DATA
    # =========================================================================

    def get_fx_rate(self, currency: str, years: int = 10) -> Dict:
        """
        Get exchange rate vs USD

        Args:
            currency: Currency code (EUR, GBP, JPY, CNY, etc.)
            years: Years of history
        """
        # Common FRED exchange rate series
        fx_series = {
            "EUR": "DEXUSEU",  # USD/EUR
            "GBP": "DEXUSUK",  # USD/GBP
            "JPY": "DEXJPUS",  # JPY/USD
            "CNY": "DEXCHUS",  # CNY/USD
            "CAD": "DEXCAUS",  # CAD/USD
            "CHF": "DEXSZUS",  # CHF/USD
            "AUD": "DEXUSAL",  # AUD/USD
            "MXN": "DEXMXUS",  # MXN/USD
        }

        series_id = fx_series.get(currency.upper())
        if not series_id:
            raise ValueError(f"Currency {currency} not supported. Available: {list(fx_series.keys())}")

        start = (datetime.now() - timedelta(days=years*365)).strftime("%Y-%m-%d")
        return self.get_series(series_id, observation_start=start)

    # =========================================================================
    # BULK DATA HELPERS
    # =========================================================================

    def get_macro_dashboard(self) -> Dict[str, Dict]:
        """
        Get key macroeconomic indicators in one call

        Returns:
            Dict with latest values for key indicators
        """
        indicators = {
            "gdp": "GDP",
            "unemployment": "UNRATE",
            "inflation_cpi": "CPIAUCSL",
            "inflation_pce": "PCEPI",
            "fed_funds": "DFF",
            "10y_treasury": "DGS10",
            "sp500": "SP500",
            "vix": "VIXCLS",
            "consumer_sentiment": "UMCSENT",
            "retail_sales": "RSXFS",
            "housing_starts": "HOUST",
            "industrial_production": "INDPRO",
            "m2_money": "M2SL",
            "employment": "PAYEMS"
        }

        dashboard = {}
        for name, series_id in indicators.items():
            try:
                data = self.get_series(series_id, limit=1, sort_order="desc")
                if data.get("observations"):
                    obs = data["observations"][0]
                    dashboard[name] = {
                        "value": obs["value"],
                        "date": obs["date"],
                        "series_id": series_id
                    }
            except Exception as e:
                dashboard[name] = {"error": str(e)}

        return dashboard


# =============================================================================
# POPULAR FRED SERIES IDS
# =============================================================================

POPULAR_SERIES = {
    # GDP & Growth
    "GDP": "Gross Domestic Product",
    "GDPC1": "Real Gross Domestic Product",
    "GDPPOT": "Real Potential Gross Domestic Product",

    # Employment
    "UNRATE": "Unemployment Rate",
    "PAYEMS": "All Employees: Total Nonfarm",
    "CIVPART": "Labor Force Participation Rate",
    "U6RATE": "Total Unemployed + Marginally Attached + Part Time",

    # Inflation
    "CPIAUCSL": "Consumer Price Index (CPI)",
    "PCEPI": "Personal Consumption Expenditures (PCE) Price Index",
    "CPILFESL": "Core CPI (ex food & energy)",

    # Interest Rates
    "DFF": "Federal Funds Effective Rate",
    "DGS10": "10-Year Treasury Constant Maturity Rate",
    "DGS2": "2-Year Treasury Constant Maturity Rate",
    "DGS30": "30-Year Treasury Constant Maturity Rate",
    "T10Y2Y": "10-Year minus 2-Year Treasury Spread",

    # Markets
    "SP500": "S&P 500",
    "VIXCLS": "CBOE Volatility Index: VIX",
    "DCOILWTICO": "Crude Oil Prices: West Texas Intermediate",
    "GOLDAMGBD228NLBM": "Gold Fixing Price",

    # Money Supply
    "M1SL": "M1 Money Stock",
    "M2SL": "M2 Money Stock",

    # Consumer
    "UMCSENT": "University of Michigan: Consumer Sentiment",
    "RSXFS": "Advance Retail Sales: Retail Trade",
    "PSAVERT": "Personal Saving Rate",

    # Housing
    "HOUST": "Housing Starts: Total",
    "MORTGAGE30US": "30-Year Fixed Rate Mortgage Average",
    "CSUSHPISA": "S&P/Case-Shiller U.S. National Home Price Index",

    # Manufacturing
    "INDPRO": "Industrial Production Index",
    "NAPM": "ISM Manufacturing: PMI Composite Index",
    "UMTMNO": "Manufacturers' New Orders: Total Manufacturing",

    # Exchange Rates
    "DEXUSEU": "U.S. / Euro Foreign Exchange Rate",
    "DEXJPUS": "Japanese Yen to U.S. Dollar",
    "DEXCHUS": "Chinese Yuan to U.S. Dollar",
}


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    # Initialize client
    client = FREDClient(api_key="f25b34228157b9daca78c742ccbbc77d")

    print("="*80)
    print("FRED CLIENT - EXAMPLE USAGE")
    print("="*80)

    # Example 1: Get GDP
    print("\n[1] Get GDP (last 5 years)")
    data = client.get_gdp(years=5)
    if data.get("observations"):
        latest = data["observations"][-1]
        print(f"Latest GDP: ${latest['value']} billion ({latest['date']})")

    # Example 2: Get Unemployment Rate
    print("\n[2] Get Unemployment Rate (last 5 years)")
    data = client.get_unemployment_rate(years=5)
    if data.get("observations"):
        latest = data["observations"][-1]
        print(f"Latest Unemployment: {latest['value']}% ({latest['date']})")

    # Example 3: Get Inflation (CPI)
    print("\n[3] Get Inflation CPI (last 5 years)")
    data = client.get_inflation_cpi(years=5)
    if data.get("observations"):
        latest = data["observations"][-1]
        print(f"Latest CPI: {latest['value']} ({latest['date']})")

    # Example 4: Get Fed Funds Rate
    print("\n[4] Get Federal Funds Rate")
    data = client.get_fed_funds_rate(years=5)
    if data.get("observations"):
        latest = data["observations"][-1]
        print(f"Latest Fed Funds: {latest['value']}% ({latest['date']})")

    # Example 5: Get 10-Year Treasury
    print("\n[5] Get 10-Year Treasury Yield")
    data = client.get_10year_treasury(years=5)
    if data.get("observations"):
        latest = data["observations"][-1]
        print(f"Latest 10Y: {latest['value']}% ({latest['date']})")

    # Example 6: Search for series
    print("\n[6] Search for 'bitcoin'")
    data = client.search_series("bitcoin", limit=3)
    if data.get("seriess"):
        print(f"Found {len(data['seriess'])} series")
        print(f"First: {data['seriess'][0]['title']}")

    # Example 7: Get exchange rate
    print("\n[7] Get EUR/USD Exchange Rate")
    data = client.get_fx_rate("EUR", years=2)
    if data.get("observations"):
        latest = data["observations"][-1]
        print(f"Latest EUR/USD: {latest['value']} ({latest['date']})")

    # Example 8: Get macro dashboard
    print("\n[8] Get Macro Dashboard (all key indicators)")
    dashboard = client.get_macro_dashboard()
    print(f"Retrieved {len(dashboard)} indicators:")
    for name, info in dashboard.items():
        if "value" in info and info["value"] != ".":
            print(f"  {name}: {info['value']} ({info.get('date', 'N/A')})")

    print("\n" + "="*80)
    print("CLIENT READY FOR USE!")
    print("="*80)
    print(f"\nTotal popular series available: {len(POPULAR_SERIES)}")
    print("\nMost useful series:")
    for series_id, description in list(POPULAR_SERIES.items())[:10]:
        print(f"  {series_id}: {description}")
