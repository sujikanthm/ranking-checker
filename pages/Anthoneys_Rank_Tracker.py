import requests
import pandas as pd
import json
import os
import time
from datetime import datetime, timedelta
import statistics

class CSEStockAnalyzer:
    def __init__(self, symbols=None, data_dir="cse_stock_data"):
        self.symbols = symbols if symbols else ["SAMP.N0000"]
        self.api_url = "https://www.cse.lk/api/companyInfoSummery"
        self.headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.cse.lk",
            "Referer": "https://www.cse.lk/"
        }
        self.data_dir = data_dir
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
        
        # Load or initialize historical data
        self.historical_data = {}
        for symbol in self.symbols:
            self.historical_data[symbol] = self._load_historical_data(symbol)
    
    def _load_historical_data(self, symbol):
        """Load historical data from JSON file if it exists"""
        file_path = os.path.join(self.data_dir, f"{symbol}_historical.json")
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return json.load(f)
        return []
    
    def _save_historical_data(self, symbol, data):
        """Save historical data to JSON file"""
        file_path = os.path.join(self.data_dir, f"{symbol}_historical.json")
        with open(file_path, 'w') as f:
            json.dump(data, f)
    
    def fetch_data(self, symbol):
        """Fetch data for a specific symbol"""
        payload = f"symbol={symbol}"
        try:
            response = requests.post(self.api_url, data=payload, headers=self.headers)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to fetch data for {symbol}. Status Code: {response.status_code}")
                return None
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
            return None

    def update_historical_data(self):
        """Update historical data for all symbols"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for symbol in self.symbols:
            data = self.fetch_data(symbol)
            if data and 'reqSymbolInfo' in data:
                symbol_info = data['reqSymbolInfo']
                beta_info = data.get('reqSymbolBetaInfo', {})
                
                # Extract relevant data
                stock_data = {
                    'timestamp': timestamp,
                    'last_traded_price': symbol_info['lastTradedPrice'],
                    'volume': symbol_info['tdyShareVolume'],
                    'turnover': symbol_info['tdyTurnover'],
                    'change': symbol_info['change'],
                    'change_percentage': symbol_info['changePercentage'],
                    'market_cap': symbol_info['marketCap'],
                    'high_price': symbol_info['hiTrade'],
                    'low_price': symbol_info['lowTrade'],
                    'previous_close': symbol_info['previousClose'],
                    'wtd_high': symbol_info['wtdHiPrice'],
                    'wtd_low': symbol_info['wtdLowPrice'],
                    'ytd_high': symbol_info['ytdHiPrice'],
                    'ytd_low': symbol_info['ytdLowPrice'],
                    'quantity_issued': symbol_info['quantityIssued'],
                    'market_cap_percentage': symbol_info['marketCapPercentage'],
                    'beta_value': beta_info.get('triASIBetaValue')
                }
                
                # Add to historical data
                self.historical_data[symbol].append(stock_data)
                
                # Save updated data
                self._save_historical_data(symbol, self.historical_data[symbol])
                
                print(f"Updated data for {symbol} at {timestamp}")
            else:
                print(f"Failed to update data for {symbol}")
    
    def analyze_data(self, symbol):
        """Analyze stock data to derive meaningful insights"""
        if symbol not in self.historical_data or not self.historical_data[symbol]:
            print(f"No data available for {symbol}")
            return None
        
        # Convert to DataFrame for analysis
        df = pd.DataFrame(self.historical_data[symbol])
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Sort by timestamp
        df = df.sort_values('timestamp')
        
        # Get latest data point
        latest = df.iloc[-1]
        
        # Calculate volatility (if we have enough data points)
        volatility = None
        if len(df) > 1:
            price_changes = df['last_traded_price'].pct_change().dropna() * 100
            volatility = price_changes.std()
        
        # Calculate moving averages (if we have enough data points)
        sma_5 = None
        sma_10 = None
        if len(df) >= 5:
            sma_5 = df['last_traded_price'].rolling(window=5).mean().iloc[-1]
        if len(df) >= 10:
            sma_10 = df['last_traded_price'].rolling(window=10).mean().iloc[-1]
        
        # Calculate relative strength (RS)
        rs = None
        if len(df) > 14:
            gains = df['change'].copy()
            losses = df['change'].copy()
            gains[gains < 0] = 0
            losses[losses > 0] = 0
            losses = losses.abs()
            avg_gain = gains.rolling(window=14).mean().iloc[-1]
            avg_loss = losses.rolling(window=14).mean().iloc[-1]
            if avg_loss != 0:
                rs = avg_gain / avg_loss
        
        # Calculate volume trend
        volume_trend = None
        if len(df) > 5:
            avg_volume_5 = df['volume'].rolling(window=5).mean().iloc[-1]
            prev_avg_volume_5 = df['volume'].rolling(window=5).mean().iloc[-6] if len(df) > 10 else df['volume'].mean()
            volume_trend = (avg_volume_5 / prev_avg_volume_5 - 1) * 100 if prev_avg_volume_5 > 0 else 0
        
        # Price momentum
        momentum = None
        if len(df) > 5:
            momentum = latest['last_traded_price'] - df['last_traded_price'].iloc[-6]
        
        # Price level relative to 52-week high and low
        price_from_high = ((latest['last_traded_price'] / latest['ytd_high']) - 1) * 100
        price_from_low = ((latest['last_traded_price'] / latest['ytd_low']) - 1) * 100
        
        # Value Metrics
        market_cap = latest['market_cap']
        market_cap_to_turnover = market_cap / latest['turnover'] if latest['turnover'] > 0 else None
        
        # Calculate trading range
        daily_range_pct = ((latest['high_price'] - latest['low_price']) / latest['previous_close']) * 100 if latest['previous_close'] > 0 else None
        
        # Beta value (market risk)
        beta = latest['beta_value']
        
        # Create analysis report
        analysis = {
            "symbol": symbol,
            "timestamp": latest['timestamp'],
            "last_price": latest['last_traded_price'],
            "daily_change": latest['change'],
            "daily_change_pct": latest['change_percentage'],
            "daily_range_pct": daily_range_pct,
            "market_cap": market_cap,
            "market_cap_percentage": latest['market_cap_percentage'],
            "volume": latest['volume'],
            "turnover": latest['turnover'],
            "beta": beta,
            "momentum": momentum,
            "volatility": volatility,
            "simple_moving_avg_5": sma_5,
            "simple_moving_avg_10": sma_10,
            "relative_strength": rs,
            "volume_trend": volume_trend,
            "price_from_ytd_high": price_from_high,
            "price_from_ytd_low": price_from_low,
            "market_cap_to_turnover": market_cap_to_turnover
        }
        
        return analysis
    
    def generate_insights(self, symbol):
        """Generate actionable insights based on analysis"""
        analysis = self.analyze_data(symbol)
        if not analysis:
            return None
        
        insights = {
            "symbol": symbol,
            "timestamp": analysis['timestamp'],
            "technical_signals": [],
            "market_position": [],
            "risk_assessment": [],
            "liquidity_analysis": [],
            "momentum_analysis": [],
            "summary": ""
        }
        
        # Technical signals
        if analysis['simple_moving_avg_5'] and analysis['simple_moving_avg_10']:
            if analysis['simple_moving_avg_5'] > analysis['simple_moving_avg_10']:
                insights['technical_signals'].append("POSITIVE: Short-term moving average above long-term - possible uptrend")
            else:
                insights['technical_signals'].append("NEGATIVE: Short-term moving average below long-term - possible downtrend")
        
        if analysis['daily_change_pct'] > 0:
            insights['technical_signals'].append(f"POSITIVE: Price up {analysis['daily_change_pct']:.2f}% today")
        elif analysis['daily_change_pct'] < 0:
            insights['technical_signals'].append(f"NEGATIVE: Price down {analysis['daily_change_pct']:.2f}% today")
        
        # Market position
        if analysis['market_cap_percentage'] > 2:
            insights['market_position'].append(f"SIGNIFICANT: Represents {analysis['market_cap_percentage']:.2f}% of total market cap")
        
        if analysis['price_from_ytd_high'] < -20:
            insights['market_position'].append(f"NOTE: Trading {abs(analysis['price_from_ytd_high']):.1f}% below 52-week high")
        elif analysis['price_from_ytd_high'] > -5:
            insights['market_position'].append(f"STRENGTH: Trading near 52-week high (within 5%)")
        
        if analysis['price_from_ytd_low'] > 50:
            insights['market_position'].append(f"STRENGTH: Trading {analysis['price_from_ytd_low']:.1f}% above 52-week low")
        elif analysis['price_from_ytd_low'] < 10:
            insights['market_position'].append(f"CAUTION: Trading near 52-week low (within 10%)")
        
        # Risk assessment
        if analysis['beta'] is not None:
            if analysis['beta'] > 1.2:
                insights['risk_assessment'].append(f"HIGH VOLATILITY: Beta of {analysis['beta']:.2f} indicates higher market risk")
            elif analysis['beta'] < 0.8:
                insights['risk_assessment'].append(f"LOW VOLATILITY: Beta of {analysis['beta']:.2f} indicates lower market risk")
            else:
                insights['risk_assessment'].append(f"MODERATE VOLATILITY: Beta of {analysis['beta']:.2f} indicates average market risk")
        
        if analysis['volatility'] is not None:
            if analysis['volatility'] > 2:
                insights['risk_assessment'].append(f"CAUTION: High price volatility ({analysis['volatility']:.2f}%)")
            elif analysis['volatility'] < 0.5:
                insights['risk_assessment'].append(f"STABLE: Low price volatility ({analysis['volatility']:.2f}%)")
        
        # Liquidity analysis
        if analysis['turnover'] > 50000000:  # 50 million LKR
            insights['liquidity_analysis'].append(f"HIGH LIQUIDITY: Daily turnover of {analysis['turnover']:,.2f} LKR")
        elif analysis['turnover'] < 5000000:  # 5 million LKR
            insights['liquidity_analysis'].append(f"LOW LIQUIDITY: Daily turnover of only {analysis['turnover']:,.2f} LKR")
        
        if analysis['volume_trend'] is not None:
            if analysis['volume_trend'] > 25:
                insights['liquidity_analysis'].append(f"INCREASING INTEREST: Volume up {analysis['volume_trend']:.1f}% compared to 5-day average")
            elif analysis['volume_trend'] < -25:
                insights['liquidity_analysis'].append(f"DECREASING INTEREST: Volume down {abs(analysis['volume_trend']):.1f}% compared to 5-day average")
        
        # Momentum analysis
        if analysis['momentum'] is not None:
            if analysis['momentum'] > 5:
                insights['momentum_analysis'].append(f"STRONG MOMENTUM: Price up {analysis['momentum']:.2f} LKR over last 5 periods")
            elif analysis['momentum'] < -5:
                insights['momentum_analysis'].append(f"NEGATIVE MOMENTUM: Price down {abs(analysis['momentum']):.2f} LKR over last 5 periods")
        
        if analysis['relative_strength'] is not None:
            if analysis['relative_strength'] > 1.2:
                insights['momentum_analysis'].append(f"STRONG RELATIVE STRENGTH: RS value of {analysis['relative_strength']:.2f}")
            elif analysis['relative_strength'] < 0.8:
                insights['momentum_analysis'].append(f"WEAK RELATIVE STRENGTH: RS value of {analysis['relative_strength']:.2f}")
        
        # Generate summary
        positive_count = sum(1 for item in insights['technical_signals'] + insights['market_position'] + 
                            insights['momentum_analysis'] if "POSITIVE" in item or "STRENGTH" in item)
        negative_count = sum(1 for item in insights['technical_signals'] + insights['market_position'] + 
                            insights['momentum_analysis'] if "NEGATIVE" in item or "CAUTION" in item)
        
        if positive_count > negative_count * 2:
            summary = f"{symbol} shows strong positive signals across multiple indicators."
        elif positive_count > negative_count:
            summary = f"{symbol} shows more positive than negative signals, but with some caution points."
        elif negative_count > positive_count * 2:
            summary = f"{symbol} shows significant weakness across multiple indicators."
        elif negative_count > positive_count:
            summary = f"{symbol} shows more negative than positive signals, suggesting caution."
        else:
            summary = f"{symbol} shows mixed signals, neither clearly positive nor negative."
        
        insights['summary'] = summary
        
        return insights
    
    def print_insights(self, symbol):
        """Print analyzed insights in a readable format"""
        insights = self.generate_insights(symbol)
        if not insights:
            return
        
        print("\n" + "="*80)
        print(f"STOCK ANALYSIS REPORT: {symbol} - {insights['timestamp']}")
        print("="*80)
        
        print("\n📊 SUMMARY:")
        print(f"  {insights['summary']}")
        
        print("\n📈 TECHNICAL SIGNALS:")
        for signal in insights['technical_signals']:
            print(f"  • {signal}")
        
        print("\n🏢 MARKET POSITION:")
        for position in insights['market_position']:
            print(f"  • {position}")
        
        print("\n⚠️ RISK ASSESSMENT:")
        for risk in insights['risk_assessment']:
            print(f"  • {risk}")
        
        print("\n💧 LIQUIDITY ANALYSIS:")
        for liquidity in insights['liquidity_analysis']:
            print(f"  • {liquidity}")
        
        print("\n🚀 MOMENTUM ANALYSIS:")
        for momentum in insights['momentum_analysis']:
            print(f"  • {momentum}")
        
        print("\n" + "="*80)
    
    def export_to_csv(self, symbol, filename=None):
        """Export historical data to CSV for further analysis"""
        if symbol not in self.historical_data or not self.historical_data[symbol]:
            print(f"No data available for {symbol}")
            return
        
        if filename is None:
            filename = os.path.join(self.data_dir, f"{symbol}_data.csv")
        
        df = pd.DataFrame(self.historical_data[symbol])
        df.to_csv(filename, index=False)
        print(f"Data exported to {filename}")

def main():
    # Initialize with stock symbols to track
    symbols = ["SAMP.N0000"]  # Add more symbols if needed
    analyzer = CSEStockAnalyzer(symbols)
    
    # Update data first
    print("Fetching latest stock data...")
    analyzer.update_historical_data()
    
    # Analyze and provide insights
    for symbol in symbols:
        analyzer.print_insights(symbol)
        analyzer.export_to_csv(symbol)  # Export for further analysis
    
    # Optional: Set up automatic periodic updates and analysis
    auto_update = input("\nDo you want to automatically update data and analysis periodically? (y/n): ")
    if auto_update.lower() == 'y':
        interval_mins = int(input("Enter update interval in minutes: "))
        interval_secs = interval_mins * 60
        try:
            print(f"Starting automatic updates every {interval_mins} minutes. Press Ctrl+C to stop.")
            while True:
                time.sleep(interval_secs)
                print(f"\nUpdating data at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")
                analyzer.update_historical_data()
                for symbol in symbols:
                    analyzer.print_insights(symbol)
                print(f"Next update in {interval_mins} minutes.")
        except KeyboardInterrupt:
            print("Automatic updates stopped.")
    
    print("\nAnalysis complete. You can find exported data in the 'cse_stock_data' directory.")

if __name__ == "__main__":
    main()