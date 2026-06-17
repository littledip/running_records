# utils.py

import pandas as pd
import altair as alt

# ─── Constants ────────────────────────────────────────────────────────────────
ERROR_COLORS = {
    "substitution": "#ff6b6b",
    "omission": "#ffa502",
    "insertion": "#7bed9f",
    "word_order": "#70a1ff",
    "self_correction": "#a4b0be",
}

ERROR_LABELS = {
    "substitution": "Substitution",
    "omission": "Omission",
    "insertion": "Insertion",
    "word_order": "Word Order",
    "self_correction": "Self-Correction",
}

# ─── Helper Functions ────────────────────────────────────────────────────────

def highlight_text(target_text: str, transcript_text: str, errors) -> dict:
    target_spans = _build_error_spans(target_text, errors, "target")
    transcript_spans = _build_error_spans(transcript_text, errors, "transcript")
    return {"target_html": target_spans["html"], "transcript_html": transcript_spans["html"]}

def _build_error_spans(text: str, errors, mode: str) -> dict:
    words = text.split()
    if not words:
        return {"html": text, "word_count": 0}
    
    word_errors = {}
    for err in errors:
        if err.target_word:
            target_words = [w.lower() for w in err.target_word.split()]
            transcript_words = [w.lower() for w in text.split()]
            for i, word in enumerate(transcript_words):
                if word in target_words or any(word == tw for tw in target_words):
                    if i not in word_errors:
                        word_errors[i] = []
                    word_errors[i].append(err)
                    
    highlighted_words = []
    for i, word in enumerate(words):
        if i in word_errors:
            error_types = [e.error_type for e in word_errors[i]]
            color = ERROR_COLORS.get(error_types[0], "#dfe4ea")
            label = " | ".join(ERROR_LABELS.get(et, et) for et in error_types)
            highlighted_words.append(
                f'<span style="background-color: {color}; padding: 2px 4px; '
                f'border-radius: 3px; margin: 1px; display: inline-block;" '
                f'title="{label}">{word}</span>'
            )
        else:
            highlighted_words.append(word)
            
    return {"html": " ".join(highlighted_words), "word_count": len(words)}

def create_error_breakdown_chart(errors):
    if not errors:
        return None
        
    error_counts = {}
    for err in errors:
        error_counts[err.error_type] = error_counts.get(err.error_type, 0) + 1
        
    df = pd.DataFrame([
        {"Error Type": ERROR_LABELS.get(et, et), "Count": count}
        for et, count in error_counts.items()
    ])
    
    label_to_color = {label: ERROR_COLORS[raw_key] for raw_key, label in ERROR_LABELS.items()}
    
    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("Error Type", sort=list(ERROR_LABELS.values()), title=""),
            y=alt.Y("Count", title="Number of Errors"),
            color=alt.Color(
                "Error Type",
                scale=alt.Scale(domain=list(label_to_color.keys()), range=list(label_to_color.values())),
                legend=None,
            ),
            tooltip=["Error Type", "Count"],
        )
        .properties(width=300, height=200)
    )
    return chart