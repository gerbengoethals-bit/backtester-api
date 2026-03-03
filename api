from http.server import BaseHTTPRequestHandler
import json
import urllib.parse

try:
    import yfinance as yf
except ImportError:
    yf = None


def get_monthly_returns(ticker_symbol: str, start: str = "2000-01-01") -> dict:
    """Fetch monthly returns for a ticker from Yahoo Finance."""
    if yf is None:
        return {"error": "yfinance not installed"}

    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(start=start, interval="1mo", auto_adjust=True)

        if hist.empty:
            return {"error": f"No data found for {ticker_symbol}"}

        # Get ticker info
        info = {}
        try:
            t_info = ticker.info
            info = {
                "name": t_info.get("longName") or t_info.get("shortName") or ticker_symbol,
                "description": t_info.get("category") or t_info.get("sector") or "",
                "currency": t_info.get("currency", "USD"),
            }
        except Exception:
            info = {"name": ticker_symbol, "description": "", "currency": "USD"}

        # Build monthly returns by year
        annual_returns = {}
        monthly_series = []

        # Calculate month-over-month returns
        closes = hist["Close"].dropna()
        returns = closes.pct_change().dropna()

        for date, ret in returns.items():
            year = date.year
            month = date.month - 1  # 0-based
            monthly_series.append({
                "year": year,
                "month": month,
                "return": round(float(ret) * 100, 4)
            })

        # Also aggregate annual returns for backward compat
        for date, ret in returns.items():
            year = date.year
            if year not in annual_returns:
                annual_returns[year] = []
            annual_returns[year].append(float(ret))

        # Compound monthly returns to get annual
        compounded = {}
        for year, rets in annual_returns.items():
            compound = 1.0
            for r in rets:
                compound *= (1 + r)
            compounded[year] = round((compound - 1) * 100, 2)

        return {
            "ticker": ticker_symbol.upper(),
            "name": info["name"],
            "description": info["description"],
            "currency": info["currency"],
            "annualReturns": compounded,
            "monthlySeries": monthly_series,
            "dataFrom": str(closes.index[0].date()) if len(closes) > 0 else "",
            "dataTo": str(closes.index[-1].date()) if len(closes) > 0 else "",
        }

    except Exception as e:
        return {"error": str(e)}


def search_tickers(query: str) -> list:
    """Search for tickers using yfinance."""
    if yf is None:
        return []
    try:
        results = yf.Search(query, max_results=8)
        quotes = results.quotes if hasattr(results, 'quotes') else []
        return [
            {
                "symbol": q.get("symbol", ""),
                "name": q.get("longname") or q.get("shortname") or q.get("symbol", ""),
                "exchange": q.get("exchange", ""),
                "type": q.get("quoteType", ""),
            }
            for q in quotes
            if q.get("symbol")
        ]
    except Exception:
        return []


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        # CORS headers
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/api/quote":
            ticker = params.get("ticker", [""])[0].upper()
            if not ticker:
                self.wfile.write(json.dumps({"error": "ticker param required"}).encode())
                return
            result = get_monthly_returns(ticker)
            self.wfile.write(json.dumps(result).encode())

        elif parsed.path == "/api/search":
            query = params.get("q", [""])[0]
            if not query:
                self.wfile.write(json.dumps([]).encode())
                return
            results = search_tickers(query)
            self.wfile.write(json.dumps(results).encode())

        else:
            self.wfile.write(json.dumps({"error": "unknown endpoint"}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        pass  # suppress default logging

