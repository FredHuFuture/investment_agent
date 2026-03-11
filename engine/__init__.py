"""Engine package — signal aggregation, drift analysis, and analysis pipeline."""

from engine.aggregator import AggregatedSignal, SignalAggregator
from engine.correlation import calculate_portfolio_correlations
from engine.drift_analyzer import DriftAnalyzer
from engine.pipeline import AnalysisPipeline
from engine.sector import SECTOR_ROTATION_MATRIX, get_sector_modifier

__all__ = [
    "AggregatedSignal",
    "AnalysisPipeline",
    "DriftAnalyzer",
    "SECTOR_ROTATION_MATRIX",
    "SignalAggregator",
    "calculate_portfolio_correlations",
    "get_sector_modifier",
]
