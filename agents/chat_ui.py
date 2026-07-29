"""Day 17 — 'Ask FleetPilot' chat UI, rendered as a view inside the existing dashboard.
Conversation memory per session (thread_id); shows the running token budget.
"""
import uuid
import streamlit as st
from chat_agent import build_chat_agent, respond, TOKEN_BUDGET

@st.cache_resource
def _agent():
    return build_chat_agent()

def render_chat():
    st.subheader("Ask FleetPilot")
    st.caption("Read-only fleet diagnostics assistant. Conversation memory is per session.")
    ss = st.session_state
    ss.setdefault("fp_thread", str(uuid.uuid4()))
    ss.setdefault("fp_msgs", [])
    ss.setdefault("fp_tokens", 0)

    for role, text in ss.fp_msgs:
        with st.chat_message(role):
            st.markdown(text)

    st.progress(min(ss.fp_tokens / TOKEN_BUDGET, 1.0),
                text=f"session tokens: {ss.fp_tokens} / {TOKEN_BUDGET}")

    prompt = st.chat_input("e.g. Which vehicle looks least healthy right now?")
    if prompt:
        ss.fp_msgs.append(("user", prompt))
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("FleetPilot is checking the fleet..."):
                reply, used, total = respond(_agent(), ss.fp_thread, prompt, ss.fp_tokens)
            st.markdown(reply)
        ss.fp_tokens = total
        ss.fp_msgs.append(("assistant", reply))

    if st.button("New session (reset memory + budget)"):
        ss.fp_thread = str(uuid.uuid4()); ss.fp_msgs = []; ss.fp_tokens = 0
        st.rerun()
