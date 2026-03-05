import streamlit as st

st.set_page_config(page_title="System-Generator", layout="centered")
st.title("System-Generator")

# Beispiel-Eingaben (später ersetzt du das durch dein echtes UI)
L = st.number_input("Länge L [m]", min_value=0.0, value=1.0, step=0.1)
EA = st.number_input("EA [kN]", min_value=0.0, value=1000.0, step=10.0)
fname = st.text_input("Dateiname", value="system.txt")

# TXT erzeugen (hier kommt deine echte Export-Logik rein)
txt = f"""# Systemdatei
L = {L}
EA = {EA}
"""

st.download_button(
    label="TXT herunterladen",
    data=txt,
    file_name=fname,
    mime="text/plain",
)
