# Alternative Assessment State Transitions (Future Consideration)

## Current Fix: Option A — Clear `assessment_active` after analysis completes

**Implementation:** In `student_record.py`, after analysis completes successfully, set `st.session_state["assessment_active"] = False`.

**Pros:** Simple, minimal code change, resolves the deadlock immediately.

**Cons:** 
- Student cannot start a new assessment without navigating back to home page
- No explicit "complete" step — transition is automatic and invisible to user
- Teacher Dashboard becomes accessible but results page (`student_results.py`) may still be displayed instead of redirecting to teacher view

---

## Option B: Full State Machine with `assessment_complete` Flag

### Concept
Introduce a three-state system:
```
IDLE → ACTIVE (recording) → COMPLETE (analysis done)
```

**State variables:**
- `assessment_active`: True while recording/analyzing
- `assessment_complete`: True after analysis finishes successfully

**Changes needed:**

1. **`student_record.py`:**
   - After analysis completes, set `assessment_complete = True` instead of clearing `assessment_active`
   - Add a "Complete Assessment & View Results" button that the user clicks to acknowledge completion

2. **`teacher_admin.py` guard update:**
   ```python
   def guard_teacher_access():
       if st.session_state.get("assessment_active", False):
           st.warning("⚠️ A student assessment is currently active...")
           return False
       # Allow access if assessment is inactive OR complete
       return True
   ```

3. **`home.py`:**
   - Reset both flags when starting a new assessment

### Pros:
- Clear state transitions visible to user
- Prevents accidental re-entry into recording during "complete" phase
- Teacher Dashboard accessible after completion without needing to navigate away
- Easier to add features like "redo assessment" or "compare results" later

### Cons:
- More session state variables to manage
- Requires updates across all three pages
- Slightly more complex logic

---

## Option C: Explicit "Complete Assessment" Button on Results Page

### Concept
Add a dedicated completion step on `student_results.py` where the user explicitly finishes the assessment.

**Changes needed:**

1. **`student_record.py`:**
   - After analysis, redirect to `student_results.py` (keep as-is)
   - Do NOT clear any flags — assessment stays "active"

2. **`student_results.py`:**
   - Display results as it currently does
   - Add a prominent **"✅ Complete Assessment"** button at the bottom
   - On click: set `assessment_complete = True`, optionally clear `assessment_active`, and redirect to Teacher Dashboard or show completion summary

3. **`teacher_admin.py` guard update:**
   ```python
   def guard_teacher_access():
       if st.session_state.get("assessment_active", False) and not st.session_state.get("assessment_complete", False):
           st.warning("⚠️ A student assessment is currently active...")
           return False
       return True
   ```

### Pros:
- User has explicit control over when assessment ends
- Natural place to show summary/next steps
- Teacher Dashboard becomes accessible after explicit completion
- Results page serves as a proper "end of session" screen rather than just a display

### Cons:
- Requires modifying `student_results.py` (which may be minimal currently)
- Adds another page to the flow
- User must remember to click "Complete" (could forget and navigate away)

---

## Recommendation

**Option A** is fine as a quick fix for now. **Option B** offers the best balance of clarity and maintainability for future development. **Option C** is worth considering if `student_results.py` needs more substantial UI work anyway.

Revisit this when:
- Students need to take multiple assessments in one session
- Teachers need to access results while a recording is still in progress (partial access)
- We want to add features like "save draft" or "resume assessment"
