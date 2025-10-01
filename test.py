import streamlit as st

st.title("Widget persistence demo")

# initialize once
st.session_state.setdefault("fname", "default_name.json")

# show current state
st.write("Current session_state:", st.session_state.get("fname"))

# text input with stable key
fname = st.text_input("File name", key="fname")

st.write("You entered:", fname)

# add a button to prove rerun doesn't reset the value
if st.button("Force rerun"):
    st.rerun()
