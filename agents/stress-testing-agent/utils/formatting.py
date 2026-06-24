"""
Display formatting helpers for the Stress Testing Agent.
All monetary values are in ₹ Crores.
"""


def fmt_cr(value: float) -> str:
    """Format a value as ₹ X Cr, rounded to nearest integer."""
    return f"₹{round(value):,} Cr"


def fmt_pct(value: float, decimals: int = 1) -> str:
    """Format a value as a percentage string."""
    return f"{value:.{decimals}f}%"


def fmt_ratio(value: float) -> str:
    """Format a ratio as X.X%  (alias for fmt_pct with 1dp)."""
    return fmt_pct(value, decimals=1)


def fmt_score(value: float) -> str:
    """Format a risk score as integer out of 100."""
    return f"{round(value)}/100"


def vulnerability_color(label: str) -> str:
    """Return a hex colour for a vulnerability label."""
    return {"High": "#DC2626", "Medium": "#D97706", "Low": "#16A34A"}.get(label, "#6B7280")
