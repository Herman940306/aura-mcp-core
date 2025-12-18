"""
Aura IA ELO Rating System

Standard ELO calculation for model rankings.
Based on chess ELO with K-factor tuned for AI debates.
"""

from typing import Tuple

# ELO Constants
INITIAL_ELO = 1500  # Starting rating for all models
ELO_K_FACTOR = 32   # Standard chess K-factor (higher = more volatile)
MIN_ELO = 100       # Floor to prevent negative ratings
MAX_ELO = 3000      # Ceiling for sanity


def expected_score(rating_a: int, rating_b: int) -> float:
    """
    Calculate expected score for player A against player B.
    
    Args:
        rating_a: ELO rating of player A
        rating_b: ELO rating of player B
    
    Returns:
        Expected probability of A winning (0.0 to 1.0)
    
    Formula:
        E(A) = 1 / (1 + 10^((Rb - Ra) / 400))
    """
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def calculate_elo_change(
    rating_a: int,
    rating_b: int,
    score_a: float,  # 1.0 = win, 0.5 = draw, 0.0 = loss
    k_factor: int = ELO_K_FACTOR,
) -> Tuple[int, int]:
    """
    Calculate ELO rating changes after a match.
    
    Args:
        rating_a: Current ELO of player A
        rating_b: Current ELO of player B
        score_a: Actual score for A (1.0 win, 0.5 draw, 0.0 loss)
        k_factor: K-factor (default 32)
    
    Returns:
        Tuple of (change_a, change_b) - rating changes for each player
    
    Formula:
        New_Ra = Ra + K * (Sa - Ea)
        
    Where:
        Sa = actual score (1, 0.5, or 0)
        Ea = expected score
    """
    expected_a = expected_score(rating_a, rating_b)
    expected_b = 1.0 - expected_a
    
    score_b = 1.0 - score_a
    
    change_a = round(k_factor * (score_a - expected_a))
    change_b = round(k_factor * (score_b - expected_b))
    
    return change_a, change_b


def update_ratings(
    rating_a: int,
    rating_b: int,
    winner: str,  # "a", "b", or "draw"
    k_factor: int = ELO_K_FACTOR,
) -> Tuple[int, int, int, int]:
    """
    Update ratings based on match outcome.
    
    Args:
        rating_a: Current ELO of player A
        rating_b: Current ELO of player B
        winner: "a" if A won, "b" if B won, "draw" for tie
        k_factor: K-factor (default 32)
    
    Returns:
        Tuple of (new_rating_a, new_rating_b, change_a, change_b)
    """
    if winner == "a":
        score_a = 1.0
    elif winner == "b":
        score_a = 0.0
    else:  # draw
        score_a = 0.5
    
    change_a, change_b = calculate_elo_change(rating_a, rating_b, score_a, k_factor)
    
    new_rating_a = max(MIN_ELO, min(MAX_ELO, rating_a + change_a))
    new_rating_b = max(MIN_ELO, min(MAX_ELO, rating_b + change_b))
    
    return new_rating_a, new_rating_b, change_a, change_b


def get_win_probability(rating_a: int, rating_b: int) -> dict:
    """
    Get win probabilities for both players.
    
    Args:
        rating_a: ELO rating of player A
        rating_b: ELO rating of player B
    
    Returns:
        Dict with win probabilities for each player
    """
    prob_a = expected_score(rating_a, rating_b)
    prob_b = 1.0 - prob_a
    
    return {
        "player_a_win": round(prob_a * 100, 1),
        "player_b_win": round(prob_b * 100, 1),
        "rating_diff": rating_a - rating_b,
        "upset_if_b_wins": prob_a > 0.6,  # B winning would be an upset
        "upset_if_a_wins": prob_b > 0.6,  # A winning would be an upset
    }


def calculate_rating_for_streak(
    current_rating: int,
    streak: int,
    opponent_ratings: list[int],
) -> int:
    """
    Calculate what rating would result from a streak against opponents.
    Useful for "what-if" scenarios.
    
    Args:
        current_rating: Starting ELO
        streak: Number of wins (positive) or losses (negative)
        opponent_ratings: List of opponent ratings faced
    
    Returns:
        Final rating after streak
    """
    rating = current_rating
    score = 1.0 if streak > 0 else 0.0
    
    for i, opp_rating in enumerate(opponent_ratings[:abs(streak)]):
        change, _ = calculate_elo_change(rating, opp_rating, score)
        rating = max(MIN_ELO, min(MAX_ELO, rating + change))
    
    return rating
