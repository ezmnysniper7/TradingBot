# utils.py
import numpy as np

def calculate_kelly_position_size(win_prob, win_loss_ratio):
    kelly_fraction = win_prob - (1 - win_prob) / win_loss_ratio
    kelly_fraction = max(0, min(kelly_fraction, 1))  # Limit between 0 and 1
    return kelly_fraction

def calculate_risk_parity_weights(volatilities):
    inv_vol = {k: 1/v for k, v in volatilities.items()}
    total_inv_vol = sum(inv_vol.values())
    weights = {k: v/total_inv_vol for k, v in inv_vol.items()}
    return weights
