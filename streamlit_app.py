import streamlit as st
import numpy as np
import pandas as pd

with st.sidebar:
    st.image("https://i.ytimg.com/vi/w3Hfj2kMrGo/maxresdefault.jpg", width=100)  # Replace with your logo URL
    st.write("Welcome to the Sensor Data Monitoring App!")
    st.write("This app allows you to monitor and visualize real-time sensor data.")
    st.write("Use the sidebar to navigate through the app.")

st.sidebar.title("Sensor Data Monitoring App")
st.sidebar.write("This app monitors real-time sensor data and visualizes it.")
st.header("Measure the data and plot them")
with st.chat_message("assistant"):
    st.write("Real time sensor readings and data visualization")
    st.bar_chart(np.random.randn(30, 3))


chart_data = pd.DataFrame(
    np.random.randn(20, 5),
    columns=["Sensor A", "Sensor B", "Sensor C", "Sensor D", "Sensor E"]
)
st.area_chart(chart_data)

with st.chat_message("assistant"):
    st.write("Real time sensor readings and data visualization")
    st.bar_chart(chart_data)

prompt = st.chat_input("Say something")
if prompt:
    st.write(f"User has sent the following prompt: {prompt}")