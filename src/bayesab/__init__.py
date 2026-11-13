"""bayesab: a small, checked implementation of classic and Bayesian A/B reads."""

from .stats import ClassicResult, BayesianResult, ABAnalysis, analyze

__all__ = ["ClassicResult", "BayesianResult", "ABAnalysis", "analyze"]
