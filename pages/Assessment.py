import streamlit as st

from src import assessment_questions as questions_lib
from ui import reset_assessment_state, setup_page, step_gate

setup_page("Assessment | Reading Assessment", icon="🧩")


def main():
    st.title("🧩 Assessment")
    st.caption(
        "Select a question and record the student's response. Standalone "
        "from Running Record; no passage/session setup needed elsewhere."
    )

    student_name = st.text_input(
        "👤 Student name",
        key="assessment_student_name_input",
        placeholder="e.g., Jane Doe",
    ).strip()

    def _reset_after_name_cleared():
        st.session_state["assessment_question_selector"] = None
        reset_assessment_state()

    if not step_gate(
        "assessment_name", student_name, reset_fn=_reset_after_name_cleared,
        prompt="Enter the student's name above to continue.",
    ):
        return

    st.session_state["current_student_name"] = student_name
    st.session_state["current_student_id"] = student_name.replace(" ", "_") or "Unknown"

    questions = questions_lib.load_assessment_questions()
    if not questions:
        st.error("❌ No assessment questions available. Please add one via the Teacher Dashboard first.")
        return

    question_options = {
        f"{qid} - {q.get('question_text', '')[:50]}": qid for qid, q in questions.items()
    }
    selected_question_label = st.selectbox(
        "❓ Select an assessment question", options=list(question_options.keys()),
        key="assessment_question_selector", index=None, placeholder="Choose a question...",
    )

    if not step_gate(
        "assessment_question", selected_question_label,
        prompt="Select a question above to reveal recording.",
    ):
        return

    question_id = question_options[selected_question_label]
    question = questions[question_id]
    st.text_area("Question", value=question.get("question_text", ""), height=100, disabled=True)

    st.info("🚧 Recording component design is still being worked out — coming soon.")


if __name__ == "__main__":
    main()
