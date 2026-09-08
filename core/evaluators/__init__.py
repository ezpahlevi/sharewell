from core.evaluation import register_evaluator, register_profile

from .execution_quality import evaluator as execution_quality
from .historical_market import evaluator as historical_market_performance
from .portfolio_outcome import evaluator as portfolio_outcome


register_evaluator(execution_quality)
register_evaluator(historical_market_performance)
register_evaluator(portfolio_outcome)
register_profile("execution-first", [{"evaluator_id": "execution_quality"}])
register_profile("momentum", [{"evaluator_id": "historical_market_performance"}])
register_profile("balanced", [{"evaluator_id": "historical_market_performance", "weight": "1"},
                               {"evaluator_id": "execution_quality", "weight": "1"}])
register_profile("risk-aware", [{"evaluator_id": "historical_market_performance",
                                 "parameters": {"metrics": ["volatility", "max_drawdown"]}}])
register_profile("verification", [{"evaluator_id": "execution_quality"},
                                    {"evaluator_id": "portfolio_outcome"}])
