import pandas as pd 
import streamlit as st 
# Every agent calls this to load data 
def load_data(uploaded_file): 
    df = pd.read_csv(uploaded_file, parse_dates=["Date"]) 
    return df 
# Every agent calls this to get clean data 
def get_clean_data(): 
    if "clean_df" not in st.session_state: 
        st.warning("Please run Data Governance Agent first") 
        st.stop() 
    return st.session_state["clean_df"]