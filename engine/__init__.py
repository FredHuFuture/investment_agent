"""Engine package — signal aggregation, drift analysis, and analysis pipeline."""

from engine.aggregator import AggregatedSignal, SignalAggregator
from engine.drift_analyzer import DriftAnalyzer
from engine.pipeline import AnalysisPipeline

__all__ = [
    "AggregatedSignal",
    "AnalysisPipeline",
    "DriftAnalyzer",
    "SignalAggregator",
]
