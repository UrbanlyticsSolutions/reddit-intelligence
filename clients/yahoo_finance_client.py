"""
Yahoo Finance Client - Free Alternative for ETF Holdings & Institutional Data
Uses yfinance library (free, no API key needed)
"""
import yfinance as yf
from typing import Dict, List, Optional, Any


class YahooFinanceClient:
    """Free Yahoo Finance client for ETF holdings and institutional data"""

    def __init__(self):
        """No API key needed - yfinance is free"""
        pass

    # ==================== ETF HOLDINGS ====================

    def get_etf_holdings(self, symbol: str) -> Dict[str, Any]:
        """
        Get ETF holdings data (top holdings)

        Args:
            symbol: ETF ticker (e.g., 'SPY', 'QQQ', 'IWM')

        Returns:
            Dict with top holdings data

        Example:
            {
                'symbol': 'SPY',
                'description': 'SPDR S&P 500 ETF Trust...',
                'top_holdings': [
                    {'symbol': 'AAPL', 'holdingPercent': 0.0712, 'holdingName': 'Apple Inc'},
                    {'symbol': 'MSFT', 'holdingPercent': 0.0635, 'holdingName': 'Microsoft Corp'}
                ],
                'total_holdings': 10
            }
        """
        try:
            ticker = yf.Ticker(symbol)
            funds_data = ticker.funds_data

            if not funds_data or not hasattr(funds_data, 'top_holdings'):
                return {
                    'symbol': symbol,
                    'error': 'No ETF holdings data available',
                    'top_holdings': [],
                    'total_holdings': 0
                }

            top_holdings = funds_data.top_holdings
            description = getattr(funds_data, 'description', '')

            # Convert to list format
            holdings_list = []
            if top_holdings is not None:
                if hasattr(top_holdings, 'to_dict'):
                    # DataFrame format
                    holdings_dict = top_holdings.to_dict('records')
                    holdings_list = holdings_dict
                elif isinstance(top_holdings, dict):
                    # Dict format
                    holdings_list = [
                        {
                            'symbol': k,
                            'holdingPercent': v.get('holdingPercent', 0) if isinstance(v, dict) else v,
                            'holdingName': v.get('holdingName', '') if isinstance(v, dict) else ''
                        }
                        for k, v in top_holdings.items()
                    ]
                elif isinstance(top_holdings, list):
                    holdings_list = top_holdings

            return {
                'symbol': symbol,
                'description': description,
                'top_holdings': holdings_list,
                'total_holdings': len(holdings_list)
            }

        except Exception as e:
            return {
                'symbol': symbol,
                'error': f'Failed to fetch ETF holdings: {str(e)}',
                'top_holdings': [],
                'total_holdings': 0
            }

    def get_etf_sector_weightings(self, symbol: str) -> Dict[str, Any]:
        """
        Get ETF sector weightings

        Args:
            symbol: ETF ticker

        Returns:
            Dict with sector allocation data
        """
        try:
            ticker = yf.Ticker(symbol)
            funds_data = ticker.funds_data

            if not funds_data:
                return {
                    'symbol': symbol,
                    'error': 'No sector data available',
                    'sector_weightings': {}
                }

            # Try to get sector weightings
            sector_weightings = {}
            if hasattr(funds_data, 'sector_weightings'):
                sector_data = funds_data.sector_weightings
                if sector_data is not None:
                    if hasattr(sector_data, 'to_dict'):
                        sector_weightings = sector_data.to_dict()
                    elif isinstance(sector_data, dict):
                        sector_weightings = sector_data

            return {
                'symbol': symbol,
                'sector_weightings': sector_weightings,
                'total_sectors': len(sector_weightings)
            }

        except Exception as e:
            return {
                'symbol': symbol,
                'error': f'Failed to fetch sector weightings: {str(e)}',
                'sector_weightings': {}
            }

    # ==================== INSTITUTIONAL HOLDERS (13F DATA) ====================

    def get_institutional_holders(self, symbol: str) -> Dict[str, Any]:
        """
        Get institutional holders (13F data)

        Args:
            symbol: Stock ticker (e.g., 'AAPL', 'MSFT')

        Returns:
            Dict with institutional holders data

        Example:
            {
                'symbol': 'AAPL',
                'holders': [
                    {
                        'Holder': 'Vanguard Group Inc',
                        'Shares': 1234567890,
                        'Date Reported': '2024-09-30',
                        'pctHeld': 0.0812,
                        'Value': 245000000000
                    }
                ],
                'total_holders': 3500
            }
        """
        try:
            ticker = yf.Ticker(symbol)
            institutional_holders = ticker.institutional_holders

            if institutional_holders is None or institutional_holders.empty:
                return {
                    'symbol': symbol,
                    'error': 'No institutional holders data available',
                    'holders': [],
                    'total_holders': 0
                }

            # Convert DataFrame to list of dicts
            holders_list = institutional_holders.to_dict('records')

            return {
                'symbol': symbol,
                'holders': holders_list,
                'total_holders': len(holders_list)
            }

        except Exception as e:
            return {
                'symbol': symbol,
                'error': f'Failed to fetch institutional holders: {str(e)}',
                'holders': [],
                'total_holders': 0
            }

    def get_major_holders(self, symbol: str) -> Dict[str, Any]:
        """
        Get major holders summary

        Args:
            symbol: Stock ticker

        Returns:
            Dict with major holders summary

        Example:
            {
                'symbol': 'AAPL',
                'institutionsPercentHeld': 0.6123,
                'insidersPercentHeld': 0.0007
            }
        """
        try:
            ticker = yf.Ticker(symbol)
            major_holders = ticker.major_holders

            if major_holders is None or major_holders.empty:
                return {
                    'symbol': symbol,
                    'error': 'No major holders data available'
                }

            # Parse major holders table
            result = {'symbol': symbol}

            # Convert to dict
            if hasattr(major_holders, 'to_dict'):
                holders_dict = major_holders.to_dict()
                result['data'] = holders_dict
            else:
                result['data'] = major_holders

            return result

        except Exception as e:
            return {
                'symbol': symbol,
                'error': f'Failed to fetch major holders: {str(e)}'
            }

    def get_mutualfund_holders(self, symbol: str) -> Dict[str, Any]:
        """
        Get mutual fund holders

        Args:
            symbol: Stock ticker

        Returns:
            Dict with mutual fund holders data
        """
        try:
            ticker = yf.Ticker(symbol)
            mutualfund_holders = ticker.mutualfund_holders

            if mutualfund_holders is None or mutualfund_holders.empty:
                return {
                    'symbol': symbol,
                    'error': 'No mutual fund holders data available',
                    'holders': [],
                    'total_holders': 0
                }

            # Convert DataFrame to list of dicts
            holders_list = mutualfund_holders.to_dict('records')

            return {
                'symbol': symbol,
                'holders': holders_list,
                'total_holders': len(holders_list)
            }

        except Exception as e:
            return {
                'symbol': symbol,
                'error': f'Failed to fetch mutual fund holders: {str(e)}',
                'holders': [],
                'total_holders': 0
            }

    # ==================== INSIDER TRADING ====================

    def get_insider_transactions(self, symbol: str) -> Dict[str, Any]:
        """
        Get insider transactions

        Args:
            symbol: Stock ticker

        Returns:
            Dict with insider transactions
        """
        try:
            ticker = yf.Ticker(symbol)
            insider_transactions = ticker.insider_transactions

            if insider_transactions is None or insider_transactions.empty:
                return {
                    'symbol': symbol,
                    'error': 'No insider transactions available',
                    'transactions': [],
                    'total_transactions': 0
                }

            # Convert DataFrame to list of dicts
            transactions_list = insider_transactions.to_dict('records')

            return {
                'symbol': symbol,
                'transactions': transactions_list,
                'total_transactions': len(transactions_list)
            }

        except Exception as e:
            return {
                'symbol': symbol,
                'error': f'Failed to fetch insider transactions: {str(e)}',
                'transactions': [],
                'total_transactions': 0
            }

    def get_insider_purchases(self, symbol: str) -> Dict[str, Any]:
        """
        Get insider purchases only

        Args:
            symbol: Stock ticker

        Returns:
            Dict with insider purchase transactions
        """
        try:
            ticker = yf.Ticker(symbol)
            insider_purchases = ticker.insider_purchases

            if insider_purchases is None or insider_purchases.empty:
                return {
                    'symbol': symbol,
                    'error': 'No insider purchases available',
                    'purchases': [],
                    'total_purchases': 0
                }

            # Convert DataFrame to list of dicts
            purchases_list = insider_purchases.to_dict('records')

            return {
                'symbol': symbol,
                'purchases': purchases_list,
                'total_purchases': len(purchases_list)
            }

        except Exception as e:
            return {
                'symbol': symbol,
                'error': f'Failed to fetch insider purchases: {str(e)}',
                'purchases': [],
                'total_purchases': 0
            }

    def get_insider_roster_holders(self, symbol: str) -> Dict[str, Any]:
        """
        Get insider roster (key insiders)

        Args:
            symbol: Stock ticker

        Returns:
            Dict with insider roster
        """
        try:
            ticker = yf.Ticker(symbol)
            insider_roster = ticker.insider_roster_holders

            if insider_roster is None or insider_roster.empty:
                return {
                    'symbol': symbol,
                    'error': 'No insider roster available',
                    'insiders': [],
                    'total_insiders': 0
                }

            # Convert DataFrame to list of dicts
            insiders_list = insider_roster.to_dict('records')

            return {
                'symbol': symbol,
                'insiders': insiders_list,
                'total_insiders': len(insiders_list)
            }

        except Exception as e:
            return {
                'symbol': symbol,
                'error': f'Failed to fetch insider roster: {str(e)}',
                'insiders': [],
                'total_insiders': 0
            }

    # ==================== UTILITY METHODS ====================

    def test_connection(self) -> bool:
        """Test if yfinance is working"""
        try:
            ticker = yf.Ticker('AAPL')
            info = ticker.info
            return info is not None and len(info) > 0
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False


# Factory function
def create_yahoo_finance_client() -> YahooFinanceClient:
    """Factory function to create Yahoo Finance client"""
    return YahooFinanceClient()
