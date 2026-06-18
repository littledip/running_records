import streamlit as st
import pandas as pd
import altair as alt

from utils import highlight_text, create_error_breakdown_chart, ERROR_LABELS

def main():
    st.title("📊 Student Results")

    # 💡 CRITICAL STEP: Read from session state
    result = st.session_state.get("last_result", None)

    if result is None:
        st.info("No results available yet. Please record a reading on the **Student Record** page first.")
        return

    st.divider()
    
    # Display Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1: 
        acc = result.metrics.accuracy if hasattr(result.metrics, 'accuracy') else 0.0
        st.metric("Accuracy", f"{acc:.0%}")
    with col2: 
        wpm = result.metrics.wpm if hasattr(result.metrics, 'wpm') else 0.0
        st.metric("Words per Minute", f"{wpm:.1f}")
    with col3: 
        total = result.metrics.total_words if hasattr(result.metrics, 'total_words') else 0
        st.metric("Total Words", total)
    with col4: 
        errs = result.metrics.error_count if hasattr(result.metrics, 'error_count') else 0
        st.metric("Errors Detected", errs)
    
    st.divider()
    
    # Display Text Comparison
    transcript_text = getattr(result, 'transcript_text', '') or ""
    
    # Note: You need to ensure highlight_text is defined in this file or imported
    highlighted = highlight_text(result.target_text, transcript_text, result.errors)
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Target Text:**", unsafe_allow_html=True)
        st.markdown(highlighted["target_html"], unsafe_allow_html=True)
    with c2:
        st.markdown("**Your Transcript:**", unsafe_allow_html=True)
        st.markdown(highlighted["transcript_html"], unsafe_allow_html=True)
        
    if result.errors:
        st.divider()
        st.subheader("🔍 Error Breakdown")
        chart = create_error_breakdown_chart(result.errors)
        if chart:
            st.altair_chart(chart, use_container_width=True)
            
        st.subheader("❌ Detailed Errors")
        error_df = pd.DataFrame([
            {
                "Type": ERROR_LABELS.get(e.error_type, e.error_type),
                "Target Word": e.target_word or "-",
                "Confidence": f"{e.confidence:.0%}" if hasattr(e, 'confidence') else "-",
                "Reason": e.reason,
            }
            for e in result.errors
        ])
        st.dataframe(error_df, use_container_width=True, hide_index=True)

if __name__ == "__main__":
    main()