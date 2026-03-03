from http.server import BaseHTTPRequestHandler
import json
import urllib.parse
import urllib.request
import urllib.error


def fetch_yahoo(ticker: str) -> dict:
    """Fetch monthly historical data directly from Yahoo Finance v8 API."""
    
    # Use a long date range: Jan 2000 to now
    period1 = "946684800"   # 2000-01-01
    period2 = "9999999999"  # far future, Yahoo clips to today
    
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(ticker)}"
        f"?interval=1mo&period1={period1}&period2={period2}&events=div"
    )
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://finance.yahoo.com/",
        "Origin": "https://finance.yahoo.com",
    }
    
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # Try backup endpoint
        url2 = url.replace("query1.finance.yahoo.com", "query2.finance.yahoo.com")
        req2 = urllib.request.Request(url2, headers=headers)
        try:
            with urllib.request.urlopen(req2, timeout=15) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except Exception as e2:
            return {"error": f"Yahoo Finance request failed: {str(e2)}"}
    except Exception as e:
        return {"error": str(e)}

    try:
        result = raw["chart"]["result"][0]
        meta = result.get("meta", {})
        timestamps = result.get("timestamp", [])
        closes = result["indicators"]["adjclose"][0]["adjclose"]
        
        if not timestamps or not closes:
            return {"error": f"No price data returned for {ticker}"}

        # Build monthly return series
        monthly_series = []
        annual_returns = {}

        prev_close = None
        for i, (ts, close) in enumerate(zip(timestamps, closes)):
            if close is None:
                continue
            
            import datetime
            dt = datetime.datetime.utcfromtimestamp(ts)
            year = dt.year
            month = dt.month - 1  # 0-based
            
            if prev_close is not None and prev_close > 0:
                ret = (close - prev_close) / prev_close * 100
                monthly_series.append({
                    "year": year,
                    "month": month,
                    "return": round(ret, 4)
                })
                # Accumulate for annual
                if year not in annual_returns:
                    annual_returns[year] = []
                annual_returns[year].append(ret / 100)
            
            prev_close = close

        # Compound monthly → annual
        compounded = {}
        for year, rets in annual_returns.items():
            compound = 1.0
            for r in rets:
                compound *= (1 + r)
            compounded[year] = round((compound - 1) * 100, 2)

        # Data range
        import datetime
        data_from = datetime.datetime.utcfromtimestamp(timestamps[0]).strftime("%Y-%m-%d") if timestamps else ""
        data_to   = datetime.datetime.utcfromtimestamp(timestamps[-1]).strftime("%Y-%m-%d") if timestamps else ""

        name = meta.get("longName") or meta.get("shortName") or ticker
        currency = meta.get("currency", "USD")
        instrument_type = meta.get("instrumentType", "")

        return {
            "ticker": ticker.upper(),
            "name": name,
            "description": instrument_type,
            "currency": currency,
            "annualReturns": compounded,
            "monthlySeries": monthly_series,
            "dataFrom": data_from,
            "dataTo": data_to,
        }

    except (KeyError, IndexError, TypeError) as e:
        return {"error": f"Failed to parse Yahoo Finance response: {str(e)}"}


def search_yahoo(query: str) -> list:
    """Search tickers using Yahoo Finance search API."""
    url = f"https://query1.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(query)}&quotesCount=8&newsCount=0&listsCount=0"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://finance.yahoo.com/",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        quotes = data.get("quotes", [])
        return [
            {
                "symbol": q.get("symbol", ""),
                "name": q.get("longname") or q.get("shortname") or q.get("symbol", ""),
                "exchange": q.get("exchDisp", q.get("exchange", "")),
                "type": q.get("typeDisp", q.get("quoteType", "")),
            }
            for q in quotes if q.get("symbol")
        ]
    except Exception as e:
        return []


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

        if parsed.path == "/api/quote":
            ticker = params.get("ticker", [""])[0].strip().upper()
            if not ticker:
                self.wfile.write(json.dumps({"error": "ticker param required"}).encode())
                return
            result = fetch_yahoo(ticker)
            self.wfile.write(json.dumps(result).encode())

        elif parsed.path == "/api/search":
            query = params.get("q", [""])[0].strip()
            if not query:
                self.wfile.write(json.dumps([]).encode())
                return
            results = search_yahoo(query)
            self.wfile.write(json.dumps(results).encode())

        else:
            self.wfile.write(json.dumps({"error": "unknown endpoint", "path": parsed.path}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        pass
