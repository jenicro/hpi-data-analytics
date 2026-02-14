"""
One-off diagnostic: run with the project venv (C:\\venvs\\hpi-data-analytics) activated.
Usage: python scripts/debug_streamlit.py
"""
import sys

print("Python:", sys.executable)
try:
    import streamlit as st
    print("Streamlit:", getattr(st, "__file__", "?"))
    print("OK – you can run: streamlit run app_org.py  or  python -m streamlit run app_org.py")
except Exception as e:
    print("Streamlit import error:", e)
    print("Install with: pip install streamlit")
