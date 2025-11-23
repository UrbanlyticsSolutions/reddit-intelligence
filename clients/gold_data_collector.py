"""
Gold Price Range Prediction - Technical Indicators Only

This script provides focused data collection for gold price range prediction:
1. Targeted data collection from FMP + FRED sources with essential indicators only
2. Data quality validation for prediction accuracy
3. TECHNICAL INDICATORS ONLY - No return calculations
4. Range-focused features (rolling ranges, position, moving averages)
5. Export formatted data ready for range prediction models
6. Flexible configuration management and command-line interface

Features:
- 12 essential financial indicators from FMP and FRED
- Technical ranges (5d, 10d, 20d)
- Moving averages (20, 50, 200)
- Technical ratios (Gold vs S&P, USD, VIX)
- Technical signals (VIX vs SMA, S&P vs SMA, etc.)
- Range expansion/compression signals

Usage:
    python gold_data_collector.py --fmp_key YOUR_FMP_KEY --fred_key YOUR_FRED_KEY
    python gold_data_collector.py --config gold_data_config.yaml --years 5

    # Or use environment variables
    export FMP_API_KEY=your_fmp_api_key
    export FRED_API_KEY=your_fred_api_key
    python gold_data_collector.py
"""

import logging
import argparse
import yaml
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any

# Local imports
from fmp_client import FMPCompleteDataClient
from fred_client import FREDClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('gold_data_collection.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ComprehensiveGoldDataCollector:
    """
    Gold price range prediction focused data collection workflow
    Collects essential indicators and calculates range prediction features
    """

    def __init__(self, fmp_api_key: str = None, fred_api_key: str = None, config: dict = None):
        """
        Initialize the comprehensive gold data collection workflow

        Args:
            fmp_api_key: FMP API key for market data (if None, will load from FMP_API_KEY env var)
            fred_api_key: FRED API key for economic data (if None, will load from FRED_API_KEY env var)
            config: Configuration dictionary
        """
        # Load API keys from environment variables if not provided
        if fmp_api_key is None:
            fmp_api_key = os.getenv('FMP_API_KEY')
            if not fmp_api_key:
                raise ValueError("FMP API key not provided and FMP_API_KEY environment variable not set")

        if fred_api_key is None:
            fred_api_key = os.getenv('FRED_API_KEY')
            if not fred_api_key:
                raise ValueError("FRED API key not provided and FRED_API_KEY environment variable not set")

        self.fmp_api_key = fmp_api_key
        self.fred_api_key = fred_api_key
        self.config = config or self._get_default_config()

        # Initialize clients
        self.fmp_client = FMPCompleteDataClient(api_key=fmp_api_key)
        self.fred_client = FREDClient(api_key=fred_api_key)

        # Define focused data sources for gold price range prediction
        self.data_sources = {
            'fmp': {
                'description': 'Financial Modeling Prep - Key Market Data for Gold',
                'indicators': {
                    # Gold Prices (Primary)
                    'gold_etf': {
                        'symbol': 'GLD',
                        'description': 'Gold ETF Price (Primary)',
                        'importance': 'critical',
                        'data_type': 'price'
                    },

                    # Key Market Factors
                    'vix': {
                        'symbol': '^VIX',
                        'description': 'CBOE Volatility Index (Market Fear)',
                        'importance': 'high',
                        'data_type': 'price'
                    },
                    'dollar_index_etf': {
                        'symbol': 'UUP',
                        'description': 'US Dollar Index ETF',
                        'importance': 'high',
                        'data_type': 'price'
                    },
                    'sp500': {
                        'symbol': '^GSPC',
                        'description': 'S&P 500 Index (Risk Appetite)',
                        'importance': 'high',
                        'data_type': 'price'
                    },
                    'treasury_10y_etf': {
                        'symbol': 'IEF',
                        'description': '10-Year Treasury ETF (Safe Haven)',
                        'importance': 'high',
                        'data_type': 'rate'
                    }
                }
            },
            'fred': {
                'description': 'Federal Reserve Economic Data - Key Drivers for Gold',
                'indicators': {
                    # Core Interest Rates (Critical for Gold)
                    'fed_funds_rate': {
                        'series_id': 'FEDFUNDS',
                        'description': 'Federal Funds Effective Rate',
                        'importance': 'critical',
                        'category': 'policy_rate'
                    },
                    'real_fed_funds': {
                        'series_id': 'DFII10',
                        'description': '10-Year Real Treasury Yield',
                        'importance': 'critical',
                        'category': 'real_rates'
                    },
                    'treasury_10y': {
                        'series_id': 'DGS10',
                        'description': '10-Year Treasury Rate',
                        'importance': 'high',
                        'category': 'market_rates'
                    },

                    # Inflation (Key Gold Driver)
                    'cpi': {
                        'series_id': 'CPIAUCSL',
                        'description': 'Consumer Price Index',
                        'importance': 'high',
                        'category': 'inflation'
                    },
                    'breakeven_10y': {
                        'series_id': 'T10YIE',
                        'description': '10-Year Breakeven Inflation Expectations',
                        'importance': 'high',
                        'category': 'inflation_expectations'
                    },

                    # Monetary Policy (QE/QT Signals)
                    'fed_total_assets': {
                        'series_id': 'WALCL',
                        'description': 'Federal Reserve Total Assets (QE/QT Indicator)',
                        'importance': 'high',
                        'category': 'balance_sheet'
                    },

                    # Yield Curve (Economic Outlook)
                    'yield_spread_10y_2y': {
                        'series_id': 'T10Y2Y',
                        'description': '10-Year minus 2-Year Treasury Spread',
                        'importance': 'high',
                        'category': 'yield_curve'
                    }
                }
            }
        }

        logger.info("Gold Price Range Prediction Data Collector initialized")
        logger.info(f"FMP indicators: {len(self.data_sources['fmp']['indicators'])}")
        logger.info(f"FRED indicators: {len(self.data_sources['fred']['indicators'])}")

        # Results storage
        self.results = {}
        self.raw_data = None
        self.processed_data = None
        self.quality_report = None

    def fetch_fmp_data(self, symbol: str, years: int = 10) -> Optional[pd.DataFrame]:
        """Fetch historical price data from FMP"""
        start_date = (datetime.now() - timedelta(days=years*365)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")

        try:
            logger.info(f"Fetching FMP data for {symbol}...")
            data = self.fmp_client.get_historical_price_eod_full(
                symbol=symbol,
                from_date=start_date,
                to_date=end_date
            )

            # Handle both list and dict responses
            if isinstance(data, list):
                if not data:
                    logger.warning(f"No FMP data found for {symbol}")
                    return None
                historical_data = data
            elif isinstance(data, dict):
                if not data.get('historical'):
                    logger.warning(f"No FMP data found for {symbol}")
                    return None
                historical_data = data['historical']
            else:
                logger.warning(f"Unexpected FMP data format for {symbol}: {type(data)}")
                return None

            # Convert to DataFrame
            df = pd.DataFrame(historical_data)
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')

            # Select relevant columns
            price_col = 'adjClose' if 'adjClose' in df.columns else 'close'
            df = df[[price_col]].copy()
            df.columns = ['value']

            logger.info(f"Successfully fetched {len(df)} observations for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Error fetching FMP data for {symbol}: {e}")
            return None

    def fetch_fred_data(self, series_id: str, years: int = 10) -> Optional[pd.DataFrame]:
        """Fetch data from FRED"""
        start_date = (datetime.now() - timedelta(days=years*365)).strftime("%Y-%m-%d")

        try:
            logger.info(f"Fetching FRED data for {series_id}...")
            data = self.fred_client.get_series(
                series_id=series_id,
                observation_start=start_date,
                sort_order="asc"
            )

            if not data.get("observations"):
                logger.warning(f"No FRED data found for {series_id}")
                return None

            # Convert to DataFrame
            df = pd.DataFrame(data["observations"])
            df['date'] = pd.to_datetime(df['date'])
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            df = df.dropna()
            df = df[['date', 'value']].set_index('date')

            logger.info(f"Successfully fetched {len(df)} observations for {series_id}")
            return df

        except Exception as e:
            logger.error(f"Error fetching FRED data for {series_id}: {e}")
            return None

    def collect_all_data(self, years: int = 10) -> pd.DataFrame:
        """Collect data from all sources and combine into single DataFrame"""
        logger.info(f"Starting comprehensive data collection for {years} years...")

        all_data = {}
        stats = {
            'fmp_success': 0,
            'fmp_failed': 0,
            'fred_success': 0,
            'fred_failed': 0
        }

        # Collect FMP data
        logger.info("Collecting FMP market data...")
        for indicator_name, config in self.data_sources['fmp']['indicators'].items():
            symbol = config['symbol']
            df = self.fetch_fmp_data(symbol, years)

            if df is not None:
                all_data[indicator_name] = df
                stats['fmp_success'] += 1
            else:
                stats['fmp_failed'] += 1
                logger.warning(f"Failed to fetch FMP data: {indicator_name} ({symbol})")

        # Collect FRED data
        logger.info("Collecting FRED economic data...")
        for indicator_name, config in self.data_sources['fred']['indicators'].items():
            series_id = config['series_id']
            df = self.fetch_fred_data(series_id, years)

            if df is not None:
                all_data[indicator_name] = df
                stats['fred_success'] += 1
            else:
                stats['fred_failed'] += 1
                logger.warning(f"Failed to fetch FRED data: {indicator_name} ({series_id})")

        # Combine all data
        if all_data:
            # Find the series with the most data as the base
            base_series = max(all_data.keys(), key=lambda k: len(all_data[k]))
            combined_df = all_data[base_series].copy()
            del all_data[base_series]

            # Join other series
            for indicator_name, df in all_data.items():
                combined_df = combined_df.join(df, how='outer', rsuffix=f'_{indicator_name}')
                # Rename the value column if needed
                if f'value_{indicator_name}' in combined_df.columns:
                    combined_df.rename(columns={f'value_{indicator_name}': indicator_name}, inplace=True)

            # Rename base series column
            if 'value' in combined_df.columns:
                combined_df.rename(columns={'value': base_series}, inplace=True)

            # Apply forward-fill for sparse economic data
            logger.info("Applying forward-fill for sparse economic data...")
            fred_columns = list(self.data_sources['fred']['indicators'].keys())

            # Apply forward-fill to FRED columns
            for col in fred_columns:
                if col in combined_df.columns:
                    original_count = combined_df[col].notna().sum()
                    # Forward-fill with limit to avoid filling too far
                    combined_df[col] = combined_df[col].fillna(method='ffill', limit=30)
                    filled_count = combined_df[col].notna().sum()
                    if filled_count > original_count:
                        logger.info(f"Forward-filled {col}: {original_count} -> {filled_count} points (+{filled_count-original_count})")

        else:
            raise ValueError("No data was successfully collected from any source")

        logger.info(f"Data collection completed:")
        logger.info(f"  FMP: {stats['fmp_success']}/{stats['fmp_success'] + stats['fmp_failed']} successful")
        logger.info(f"  FRED: {stats['fred_success']}/{stats['fred_success'] + stats['fred_failed']} successful")
        logger.info(f"Combined DataFrame shape: {combined_df.shape}")

        return combined_df

    def calculate_derived_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate HIGHLY RELEVANT technical indicators for gold price range prediction"""
        logger.info("Calculating highly relevant technical indicators...")

        # Gold price identification
        gold_col = 'gold_etf'  # Primary gold indicator

        if gold_col and gold_col in df.columns:
            # HIGHLY RELEVANT: Rolling ranges (KEY for range prediction)
            df['gold_high_20d'] = df[gold_col].rolling(window=20).max()
            df['gold_low_20d'] = df[gold_col].rolling(window=20).min()
            df['gold_range_20d'] = df['gold_high_20d'] - df['gold_low_20d']
            df['gold_range_pct_20d'] = (df['gold_range_20d'] / df[gold_col]) * 100

            df['gold_range_5d'] = df[gold_col].rolling(window=5).max() - df[gold_col].rolling(window=5).min()

            # HIGHLY RELEVANT: Price position within range
            df['gold_position_20d'] = (df[gold_col] - df['gold_low_20d']) / df['gold_range_20d']

            # HIGHLY RELEVANT: Technical momentum vs 20d moving average
            df['gold_ma_20'] = df[gold_col].rolling(window=20).mean()
            df['gold_vs_ma20'] = (df[gold_col] / df['gold_ma_20'] - 1) * 100

            # MODERATELY RELEVANT: Price momentum
            df['gold_momentum_20d'] = (df[gold_col] - df[gold_col].shift(20)) / df[gold_col].shift(20)

            logger.info(f"Calculated core technical indicators using {gold_col}")

        # HIGHLY RELEVANT: Market fear/volatility
        if 'vix' in df.columns:
            df['vix_normalized'] = (df['vix'] - df['vix'].rolling(60).mean()) / df['vix'].rolling(60).std()

        # MODERATELY RELEVANT: Key ratios for range drivers
        if gold_col and 'sp500' in df.columns:
            df['gold_sp500_ratio'] = df[gold_col] / df['sp500']
        if gold_col and 'vix' in df.columns:
            df['gold_vix_ratio'] = df[gold_col] / df['vix']

        # Yield curve signal (MODERATELY relevant)
        if 'yield_spread_10y_2y' in df.columns:
            df['yield_curve_inverted'] = (df['yield_spread_10y_2y'] < 0).astype(int)

        # HIGHLY RELEVANT: Range expansion signal (composite)
        range_expansion_signals = []
        if gold_col and 'gold_range_pct_20d' in df.columns:
            range_expansion_signals.append(df['gold_range_pct_20d'] > df['gold_range_pct_20d'].rolling(60).quantile(0.75))
        if 'vix_normalized' in df.columns:
            range_expansion_signals.append(df['vix_normalized'] > 1.0)
        if 'yield_curve_inverted' in df.columns:
            range_expansion_signals.append(df['yield_curve_inverted'])

        if range_expansion_signals:
            df['range_expansion_signal'] = sum(range_expansion_signals).astype(int)
            logger.info("Calculated range expansion signal")

        return df

    def _get_default_config(self) -> dict:
        """Get default configuration"""
        return {
            'data_collection': {
                'years': 5,
                'validate_quality': True,
                'save_raw_data': True,
                'save_processed_data': True
            },
            'data_processing': {
                'calculate_derived_indicators': True,
                'handle_missing_data': True,
                'missing_data_strategy': 'hybrid'  # 'forward_fill', 'interpolate', 'hybrid'
            },
            'quality_control': {
                'min_completeness_threshold': 0.8,
                'max_missing_consecutive_days': 5,
                'outlier_detection': True,
                'outlier_threshold': 3.0
            },
            'analysis': {
                'generate_correlation_matrix': True,
                'identify_top_indicators': True,
                'calculate_basic_statistics': True
            },
            'output': {
                'save_results': True,
                'generate_report': False,  # Disable report generation
                'export_formats': ['csv'],  # Only CSV format
                'output_dir': 'gold_data_output'
            }
        }

    def validate_data_quality(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Comprehensive data quality validation"""
        validation_report = {
            'summary': {
                'total_rows': len(df),
                'total_columns': len(df.columns),
                'date_range': f"{df.index.min().date()} to {df.index.max().date()}",
                'data_sources': {}
            },
            'column_analysis': {},
            'data_quality_score': 0,
            'recommendations': []
        }

        # Analyze each column
        high_quality_cols = 0
        total_cols = len(df.columns)

        for col in df.columns:
            col_data = df[col].dropna()
            total_points = len(df)
            valid_points = len(col_data)

            if valid_points == 0:
                quality_score = 0
                status = "Empty"
            else:
                completeness = valid_points / total_points
                if completeness >= 0.95:
                    quality_score = 100
                    status = "Excellent"
                elif completeness >= 0.80:
                    quality_score = 80
                    status = "Good"
                elif completeness >= 0.50:
                    quality_score = 50
                    status = "Fair"
                else:
                    quality_score = 25
                    status = "Poor"

                if quality_score >= 80:
                    high_quality_cols += 1

            # Determine data source
            source = "unknown"
            for indicator_name, config in self.data_sources['fmp']['indicators'].items():
                if col == indicator_name:
                    source = "FMP"
                    break
            if source == "unknown":
                for indicator_name, config in self.data_sources['fred']['indicators'].items():
                    if col == indicator_name:
                        source = "FRED"
                        break
            if source == "unknown":
                source = "Calculated"

            validation_report['column_analysis'][col] = {
                'total_points': total_points,
                'valid_points': valid_points,
                'completeness': completeness if valid_points > 0 else 0,
                'quality_score': quality_score,
                'status': status,
                'source': source,
                'first_date': col_data.index.min().date() if valid_points > 0 else None,
                'last_date': col_data.index.max().date() if valid_points > 0 else None
            }

        # Calculate overall quality score
        validation_report['data_quality_score'] = (high_quality_cols / total_cols) * 100 if total_cols > 0 else 0
        validation_report['summary']['high_quality_columns'] = high_quality_cols

        # Source summary
        source_stats = {}
        for col, analysis in validation_report['column_analysis'].items():
            source = analysis['source']
            if source not in source_stats:
                source_stats[source] = {'count': 0, 'total_quality': 0}
            source_stats[source]['count'] += 1
            source_stats[source]['total_quality'] += analysis['quality_score']

        for source, stats in source_stats.items():
            avg_quality = stats['total_quality'] / stats['count'] if stats['count'] > 0 else 0
            validation_report['summary']['data_sources'][source] = {
                'count': stats['count'],
                'avg_quality': avg_quality
            }

        # Generate recommendations
        if validation_report['data_quality_score'] < 80:
            validation_report['recommendations'].append("Overall data quality needs improvement")

        # Check for critical missing data
        critical_indicators = ['gold_etf', 'fed_funds_rate', 'real_fed_funds_calculated']
        missing_critical = [col for col in critical_indicators if col not in df.columns or validation_report['column_analysis'].get(col, {}).get('completeness', 0) < 0.8]
        if missing_critical:
            validation_report['recommendations'].append(f"Missing critical indicators: {missing_critical}")

        # Check for sufficient history
        if len(df) < 252:
            validation_report['recommendations'].append("Insufficient historical data - recommend at least 1 year")

        logger.info(f"Data validation completed. Quality score: {validation_report['data_quality_score']:.1f}%")
        return validation_report

    def get_data_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get comprehensive summary of the collected data"""
        logger.info("Generating comprehensive data summary...")

        summary = {
            'overview': {
                'period': f"{df.index.min().date()} to {df.index.max().date()}",
                'total_days': len(df),
                'indicators_count': len(df.columns),
                'data_sources': len(set([col.split('_')[0] for col in df.columns if '_' in col]))
            },
            'gold_data': {},
            'key_relationships': {},
            'data_coverage': {}
        }

        # Gold data summary
        gold_col = 'gold_etf'  # Primary gold indicator

        if gold_col in df.columns:
            gold_data = df[gold_col].dropna()
            if len(gold_data) > 0:
                summary['gold_data'] = {
                    'source': gold_col,
                    'current_price': float(gold_data.iloc[-1]),
                    'min_price': float(gold_data.min()),
                    'max_price': float(gold_data.max()),
                    'avg_price': float(gold_data.mean()),
                    'volatility': float(gold_data.pct_change().std() * np.sqrt(252) * 100),
                    'total_return': ((gold_data.iloc[-1] / gold_data.iloc[0]) - 1) * 100,
                    'data_points': len(gold_data)
                }

        # Key correlations
        if gold_col:
            correlations = {}
            for col in df.columns:
                if col != gold_col and df[col].dtype in ['float64', 'int64'] and df[col].notna().sum() > 10:
                    corr = df[col].corr(df[gold_col])
                    if not np.isnan(corr):
                        correlations[col] = corr

            sorted_correlations = dict(sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True))
            summary['key_relationships'] = {
                'top_positive': {k: v for k, v in list(sorted_correlations.items())[:5] if v > 0.1},
                'top_negative': {k: v for k, v in list(sorted_correlations.items())[:5] if v < -0.1},
                'all_correlations': sorted_correlations
            }

        # Data coverage by source
        source_coverage = {}
        for col in df.columns:
            if 'etf' in col or 'sp500' in col or 'vix' in col or 'dollar' in col:
                source = 'FMP'
            elif any(x in col for x in ['fed_', 'treasury_', 'cpi', 'gdp', 'unemployment', 'yield_', 'm1_', 'm2_']):
                source = 'FRED'
            else:
                source = 'Calculated'

            if source not in source_coverage:
                source_coverage[source] = {'count': 0, 'total_coverage': 0}

            coverage = (df[col].notna().sum() / len(df)) * 100
            source_coverage[source]['count'] += 1
            source_coverage[source]['total_coverage'] += coverage

        for source, stats in source_coverage.items():
            stats['avg_coverage'] = stats['total_coverage'] / stats['count']
            summary['data_coverage'][source] = {
                'indicators': stats['count'],
                'avg_coverage_pct': stats['avg_coverage']
            }

        logger.info("Comprehensive data summary generated")
        return summary

    def run_complete_workflow(self) -> dict:
        """
        Run the gold price range prediction focused data collection workflow

        Returns:
            Complete results dictionary with data and analysis
        """
        logger.info("Starting gold price range prediction data collection...")

        try:
            # Step 1: Raw Data Collection
            logger.info("Step 1/5: Collecting focused data from FMP and FRED...")
            self.raw_data = self.collect_all_data(self.config['data_collection']['years'])

            # Step 2: Data Quality Validation
            logger.info("Step 2/5: Validating data quality...")
            quality_results = self.validate_data_quality(self.raw_data)

            # Step 3: Data Processing with range-focused indicators
            logger.info("Step 3/5: Processing data and calculating range indicators...")
            self.processed_data = self.calculate_derived_indicators(self.raw_data)

            # Step 4: Clean Missing Data
            logger.info("Step 4/5: Cleaning missing data...")
            # Use forward-fill for technical indicator gaps, then drop remaining NaNs
            before_rows = len(self.processed_data)

            # Forward fill technical indicators with reasonable limits
            for col in ['gold_ma_20', 'gold_position_20d', 'gold_vs_ma20', 'gold_momentum_20d']:
                if col in self.processed_data.columns:
                    self.processed_data[col] = self.processed_data[col].fillna(method='ffill', limit=60)

            for col in ['vix_normalized']:
                if col in self.processed_data.columns:
                    self.processed_data[col] = self.processed_data[col].fillna(method='ffill', limit=120)

            # Drop rows where essential gold data is still missing
            essential_cols = ['gold_etf', 'gold_ma_20', 'gold_position_20d']
            self.processed_data = self.processed_data.dropna(subset=essential_cols, how='any')

            after_rows = len(self.processed_data)
            logger.info(f"Cleaned data: {before_rows} -> {after_rows} rows ({before_rows - after_rows} dropped)")
            logger.info(f"Data completeness: {(after_rows/before_rows)*100:.1f}%")

            # Step 5: Export
            logger.info("Step 5/5: Exporting data...")
            export_results = self._export_data_and_reports()

            # Compile results
            self.results = {
                'workflow_info': {
                    'execution_time': datetime.now().isoformat(),
                    'config': self.config,
                    'status': 'completed',
                    'workflow_type': 'gold_range_prediction_data_collection'
                },
                'data_collection': {
                    'raw_data_shape': self.raw_data.shape if self.raw_data is not None else None,
                    'processed_data_shape': self.processed_data.shape if self.processed_data is not None else None,
                    'date_range': f"{self.processed_data.index.min().date()} to {self.processed_data.index.max().date()}" if self.processed_data is not None else None
                },
                'quality_results': quality_results,
                'analysis_results': self.get_data_summary(self.processed_data),
                'export_results': export_results
            }

            # Save results if configured
            if self.config['output']['save_results']:
                self._save_workflow_results()

            logger.info("Gold range prediction data collection finished successfully!")
            return self.results

        except Exception as e:
            logger.error(f"Data collection workflow failed: {e}")
            self.results = {
                'workflow_info': {
                    'execution_time': datetime.now().isoformat(),
                    'config': self.config,
                    'status': 'failed',
                    'error': str(e)
                }
            }
            raise

    def _collect_raw_data(self) -> pd.DataFrame:
        """Collect raw data from all sources - legacy method for compatibility"""
        return self.collect_all_data(self.config['data_collection']['years'])

    def _validate_data_quality(self) -> dict:
        """Validate raw data quality - legacy method for compatibility"""
        return self.validate_data_quality(self.raw_data)

    def _process_data(self) -> pd.DataFrame:
        """Process and clean the raw data - legacy method for compatibility"""
        if self.raw_data is None:
            raise ValueError("Raw data not collected")

        logger.info("Processing and cleaning data...")
        processed_data = self.raw_data.copy()

        # Calculate derived indicators if configured
        if self.config['data_processing']['calculate_derived_indicators']:
            logger.info("Calculating derived indicators...")
            processed_data = self.calculate_derived_indicators(processed_data)

        # Handle missing data if configured
        if self.config['data_processing']['handle_missing_data']:
            logger.info("Handling missing data...")
            strategy = self.config['data_processing']['missing_data_strategy']
            processed_data = self._handle_missing_data(processed_data, strategy)

        # Detect and handle outliers if configured
        if self.config['quality_control']['outlier_detection']:
            logger.info("Detecting and handling outliers...")
            processed_data = self._handle_outliers(processed_data)

        logger.info(f"Data processing completed. Shape: {processed_data.shape}")
        return processed_data

    def _analyze_data(self) -> dict:
        """Analyze data relationships and patterns - legacy method for compatibility"""
        return self.get_data_summary(self.processed_data)

    def _handle_missing_data(self, df: pd.DataFrame, strategy: str) -> pd.DataFrame:
        """Handle missing data using specified strategy"""
        result = df.copy()
        improvements = []

        if strategy == 'forward_fill':
            # Forward fill up to N consecutive days
            max_consecutive = self.config['quality_control']['max_missing_consecutive_days']
            for col in result.columns:
                before_completeness = (result[col].notna().sum() / len(result)) * 100
                result[col] = result[col].fillna(method='ffill', limit=max_consecutive)
                after_completeness = (result[col].notna().sum() / len(result)) * 100
                if after_completeness > before_completeness:
                    improvements.append((col, after_completeness - before_completeness))

        elif strategy == 'interpolate':
            # Time-based interpolation
            for col in result.columns:
                before_completeness = (result[col].notna().sum() / len(result)) * 100
                if 'rate' in col or 'yield' in col or 'spread' in col:
                    result[col] = result[col].interpolate(method='time')
                else:
                    result[col] = result[col].interpolate(method='linear')
                after_completeness = (result[col].notna().sum() / len(result)) * 100
                if after_completeness > before_completeness:
                    improvements.append((col, after_completeness - before_completeness))

        elif strategy == 'hybrid':
            # Combination of strategies
            max_consecutive = self.config['quality_control']['max_missing_consecutive_days']

            for col in result.columns:
                before_completeness = (result[col].notna().sum() / len(result)) * 100

                # Forward fill short gaps
                result[col] = result[col].fillna(method='ffill', limit=max_consecutive)

                # Interpolate remaining gaps
                if 'rate' in col or 'yield' in col or 'spread' in col:
                    result[col] = result[col].interpolate(method='time', limit=10)
                else:
                    result[col] = result[col].interpolate(method='linear', limit=10)

                after_completeness = (result[col].notna().sum() / len(result)) * 100
                if after_completeness > before_completeness:
                    improvements.append((col, after_completeness - before_completeness))

        if improvements:
            avg_improvement = np.mean([imp for _, imp in improvements])
            logger.info(f"Missing data handling improved completeness by {avg_improvement:.2f}% on average")

        return result

    def _handle_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect and handle outliers"""
        result = df.copy()
        threshold = self.config['quality_control']['outlier_threshold']
        outliers_handled = []

        for col in result.select_dtypes(include=[np.number]).columns:
            if col in result.columns and not result[col].isna().all():
                # Calculate Z-scores
                z_scores = np.abs((result[col] - result[col].mean()) / result[col].std())
                outlier_mask = z_scores > threshold

                if outlier_mask.any():
                    # Cap outliers at threshold instead of removing them
                    upper_bound = result[col].mean() + threshold * result[col].std()
                    lower_bound = result[col].mean() - threshold * result[col].std()

                    result[col] = result[col].clip(lower_bound, upper_bound)
                    outliers_handled.append(col)
                    logger.debug(f"Capped {outlier_mask.sum()} outliers in {col}")

        if outliers_handled:
            logger.info(f"Outliers handled in {len(outliers_handled)} columns")

        return result

    def _export_data_and_reports(self) -> dict:
        """Export data and generate reports - ONLY 1 CSV OUTPUT"""
        if not self.config['output']['save_results']:
            return {'status': 'skipped', 'reason': 'Save disabled in config'}

        logger.info("Exporting data and reports...")

        output_dir = Path(self.config['output']['output_dir'])
        output_dir.mkdir(exist_ok=True)

        export_results = {
            'status': 'completed',
            'output_dir': str(output_dir),
            'files_created': []
        }

        # Export ONLY 1 CSV file with processed data
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            filename = output_dir / f"gold_data.csv"
            self.processed_data.to_csv(filename)
            export_results['files_created'].append(str(filename))
            logger.info(f"Exported 1 CSV file: {filename}")
        except Exception as e:
            logger.error(f"Failed to export CSV: {e}")
            raise

        logger.info(f"Export completed. Files created: {len(export_results['files_created'])}")
        return export_results

    def _save_workflow_results(self):
        """Save workflow results to JSON file"""
        try:
            output_dir = Path(self.config['output']['output_dir'])
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            results_file = output_dir / f"workflow_results_pure_{timestamp}.json"

            # Convert numpy types for JSON serialization
            def convert_numpy(obj):
                if isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, pd.Timestamp):
                    return obj.isoformat()
                elif isinstance(obj, (pd.DataFrame, pd.Series)):
                    return obj.to_dict()
                elif hasattr(obj, '__dict__'):
                    return str(obj)
                return obj

            with open(results_file, 'w') as f:
                json.dump(self.results, f, indent=2, default=convert_numpy)

            logger.info(f"Workflow results saved to {results_file}")
        except Exception as e:
            logger.warning(f"Could not save workflow results to JSON: {e}")

    def _generate_comprehensive_report(self):
        """Generate comprehensive data collection report"""
        output_dir = Path(self.config['output']['output_dir'])
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = output_dir / f"gold_data_collection_report_pure_{timestamp}.txt"

        report = f"""
PURE GOLD DATA COLLECTION REPORT
{'='*80}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Workflow Type: Pure Data Collection
Status: {self.results['workflow_info']['status']}

DATA SUMMARY
{'='*50}
Data Range: {self.results['data_collection']['date_range']}
Raw Data Shape: {self.results['data_collection']['raw_data_shape']}
Processed Data Shape: {self.results['data_collection']['processed_data_shape']}

DATA QUALITY
{'='*50}
Overall Quality Score: {self.results['quality_results']['overall_quality_score']:.1%}
Total Columns: {self.results['quality_results']['total_columns']}
High Quality Columns: {self.results['quality_results']['high_quality_columns']}
Issues Found: {self.results['quality_results']['issues_found']}

Data Sources: {', '.join(self.results['quality_results']['data_sources'].keys())}

TOP INDICATORS
{'='*50}
"""

        # Add top indicators if available
        top_indicators = self.results['analysis_results'].get('top_indicators', {})
        if top_indicators:
            for indicator, metrics in list(top_indicators.items())[:10]:
                report += f"{indicator}: Score={metrics['score']:.3f}, "
                report += f"Quality={metrics['completeness']:.1%}, "
                report += f"Correlation={metrics['correlation_with_gold']:.3f}\n"
        else:
            report += "No top indicators identified\n"

        report += f"""
RECOMMENDATIONS
{'='*50}
"""
        # Add recommendations
        recommendations = self.results['quality_results'].get('recommendations', [])
        if recommendations:
            for i, rec in enumerate(recommendations, 1):
                report += f"{i}. {rec}\n"
        else:
            report += "No specific recommendations\n"

        report += f"""
EXPORT INFORMATION
{'='*50}
Files Created: {len(self.results['export_results'].get('files_created', []))}
Output Directory: {self.results['export_results'].get('output_dir', 'N/A')}

CONFIGURATION USED
{'='*50}
Data Collection Years: {self.config['data_collection']['years']}
Missing Data Strategy: {self.config['data_processing']['missing_data_strategy']}
Derived Indicators: {self.config['data_processing']['calculate_derived_indicators']}
Outlier Detection: {self.config['quality_control']['outlier_detection']}

"""

        # Write report
        with open(report_file, 'w') as f:
            f.write(report)

        logger.info(f"Comprehensive report saved to {report_file}")


def load_config(config_file: str) -> dict:
    """Load configuration from YAML file"""
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        logger.info(f"Configuration loaded from {config_file}")
        return config
    except Exception as e:
        logger.error(f"Failed to load config file {config_file}: {e}")
        return None


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description='Pure Gold Data Collection Workflow')
    parser.add_argument('--fmp_key', help='FMP API key (can also be set via FMP_API_KEY env var)')
    parser.add_argument('--fred_key', help='FRED API key (can also be set via FRED_API_KEY env var)')
    parser.add_argument('--config', help='Configuration file (YAML)')
    parser.add_argument('--years', type=int, default=5, help='Years of data to collect')
    parser.add_argument('--output_dir', default='gold_data_output', help='Output directory')
    parser.add_argument('--formats', nargs='+', default=['csv'],
                       choices=['csv', 'json'], help='Export formats')

    args = parser.parse_args()

    # Load API keys from environment variables if not provided as arguments
    fmp_key = args.fmp_key or os.getenv('FMP_API_KEY')
    fred_key = args.fred_key or os.getenv('FRED_API_KEY')

    # Validate that API keys are available
    if not fmp_key:
        raise ValueError("FMP API key must be provided via --fmp_key argument or FMP_API_KEY environment variable")
    if not fred_key:
        raise ValueError("FRED API key must be provided via --fred_key argument or FRED_API_KEY environment variable")

    # Load configuration
    config = None
    if args.config:
        config = load_config(args.config)
        if config:
            # Override with command line arguments
            if args.years:
                config['data_collection']['years'] = args.years
            config['output']['output_dir'] = args.output_dir
            config['output']['export_formats'] = args.formats

    # Initialize and run workflow
    try:
        logger.info("Starting Gold Price Range Prediction Data Collection")
        logger.info(f"FMP API Key: {fmp_key[:10]}...")
        logger.info(f"FRED API Key: {fred_key[:10]}...")

        workflow = ComprehensiveGoldDataCollector(
            fmp_api_key=fmp_key,
            fred_api_key=fred_key,
            config=config
        )

        results = workflow.run_complete_workflow()

        # Print summary
        print("\n" + "="*80)
        print("GOLD PRICE RANGE PREDICTION DATA COLLECTION COMPLETED")
        print("="*80)

        data_info = results['data_collection']
        print(f"Data Range: {data_info['date_range']}")
        print(f"Final Data Shape: {data_info['processed_data_shape']}")

        quality = results['quality_results']
        print(f"Data Quality Score: {quality['data_quality_score']:.1f}%")

        export_info = results['export_results']
        print(f"Files Created: {len(export_info.get('files_created', []))}")
        print(f"Output Directory: {export_info.get('output_dir', 'N/A')}")

        print(f"\nRange prediction data collection completed successfully!")
        print("="*80)

    except Exception as e:
        logger.error(f"Data collection workflow failed: {e}")
        print(f"\nWorkflow failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())