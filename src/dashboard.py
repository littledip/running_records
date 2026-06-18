# src/dashboard.py
import altair as alt
import pandas as pd
from typing import List, Dict, Any

def create_error_breakdown_chart(errors: List[Dict[str, Any]]) -> alt.Chart:
    """Creates a horizontal bar chart for error types."""
    if not errors:
        return alt.Chart(pd.DataFrame()).mark_text(
            text="No errors detected 🎉"
        ).encode(y=alt.Y('N()'))

    df = pd.DataFrame(errors)
    
    # Define color domain to match your data labels
    chart = alt.Chart(df).mark_bar().encode(
        x='count:Q',
        y=alt.Y('error_type:N', sort='-x'),
        color=alt.Color('error_type:N', 
                        scale=alt.Scale(domain=['substitution', 'omission', 'addition'],
                                        range=['#ff6b6b', '#ffa502', '#70a1ff']),
                        legend=None),
        tooltip=['error_type', 'detail']
    ).properties(
        width=300,
        height=200,
        title="Error Breakdown"
    )
    
    return chart

def create_performance_metrics(metrics: Dict[str, Any]) -> pd.DataFrame:
    """Returns a DataFrame for the dashboard summary."""
    return pd.DataFrame({
        'Metric': ['Accuracy', 'WPM', 'Total Words', 'Errors'],
        'Value': [
            f"{metrics['accuracy']*100:.1f}%",
            f"{metrics['wpm']:.1f}",
            str(metrics['total_words']),
            str(metrics['error_count'])
        ]
    })
