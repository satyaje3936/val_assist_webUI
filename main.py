import streamlit as st
from multiapp import MultiApp
# from pages.Utilities import Hex_Decoder, Mermaid_Diagram_Generator  # Import the new page
import logging

# from pages.Analyzers import Bios_Log_Analyzer, HSD_Analyzer, Rocket_Config_File_Analyzer, Source_Code_Analyzer, Bulk_HSD_Analyzer, PVIM_Test_Plan_Analyzer  # Import the new page
# from pages.Test_Planning import PVIM_Test_Plan_Assessment
# from pages.template import template
from General import Home, Settings, About  # Import the new pages
from Tools import Chat_With_AI  # Import the new page
#from Tools import FCCB_Hsd_Analysis  # Import the new page
from Tools import HSD_Query_Summary_App  # Import the new Streamlit HSD app
from Tools import FCCB_HSD_Query_Summary_App  # Import the new FCCB Streamlit app
# from Tools import hsd_query_summary  # Commented out: CLI tool, not Streamlit app
#from pages.Streamlit_Demo import basic_charts, data_tables, interactive_plots, machine_learning, maps_and_geospatial  # Import Streamlit demo pages

# Initialize logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[
    logging.FileHandler("genAI-Val-Assistant-WebUI.log"),
    logging.StreamHandler()
])
logger = logging.getLogger(__name__)

app = MultiApp()

# Add all your application here
# logger.info("Adding PVIM Test Plan Assessment app")
# app.add_app("Test_Planning", "PVIM Test Plan Assessment", PVIM_Test_Plan_Assessment.app)  # Update the page name

logger.info("Adding Trial test to check Open AI API")
app.add_app("Tools", "Chat with AI", Chat_With_AI.app)

# logger.info("Adding FCCB HSD analysis")
# app.add_app("Tools", "Fuse CCB HSD Analysis", FCCB_Hsd_Analysis.app)

logger.info("Adding HSD Query Summary app")
app.add_app("Tools", "HSD Query Summary", HSD_Query_Summary_App.app)  # Add the new Streamlit HSD app

logger.info("Adding FCCB HSD Query Summary app")
app.add_app("Tools", "FCCB HSD Query Summary", FCCB_HSD_Query_Summary_App.app)  # Add the new FCCB Streamlit app

# logger.info("Adding Sightings(HSD) Summary app")
# app.add_app("Tools", "Sightings(HSD) Summary", hsd_query_summary.app)  # Add the new page - Commented out: hsd_query_summary.py is a CLI tool, not a Streamlit app

# logger.info("Adding Single HSD Analyzer app")
# app.add_app("Analyzers", "HSD Analyzer", HSD_Analyzer.app)  # Add the new page

# logger.info("Adding Bulk HSD Analyzer app")
# app.add_app("Analyzers", "Bulk HSD Analyzer", Bulk_HSD_Analyzer.app)  # Add the new page

# logger.info("Adding PVIM Test Plan Analyzer app")
# app.add_app("Analyzers", "PVIM Test Plan Analyzer", PVIM_Test_Plan_Analyzer.app)  # Add the new page

# logger.info("Adding Mermaid Diagram Generator app")
# app.add_app("Utilities", "Mermaid Diagram Generator", Mermaid_Diagram_Generator.app)  # Add the new page

# logger.info("Adding Hex Calculator app")
# app.add_app("Utilities", "Hex Calculator", Hex_Decoder.app)  # Add the new page

# logger.info("Adding Template app")
# app.add_app("Template", "Template", template.app)  # Add the new page

logger.info("Adding Home app")
app.add_app("General", "Home", Home.app)  # Add the new page

logger.info("Adding Settings app")
app.add_app("General", "Settings", Settings.app)  # Add the new page

logger.info("Adding About app")
app.add_app("General", "About", About.app)  # Add the new page

# Add Streamlit demo pages
#logger.info("Adding Basic Charts app")
#app.add_app("Streamlit Demo", "Basic Charts", basic_charts.app)

#logger.info("Adding Data Tables app")
#app.add_app("Streamlit Demo", "Data Tables", data_tables.app)

#logger.info("Adding Interactive Plots app")
#app.add_app("Streamlit Demo", "Interactive Plots", interactive_plots.app)

#logger.info("Adding Machine Learning app")
#app.add_app("Streamlit Demo", "Machine Learning", machine_learning.app)

#logger.info("Adding Maps and Geospatial app")
#app.add_app("Streamlit Demo", "Maps and Geospatial", maps_and_geospatial.app)

# The main app
logger.info("Running the main app")
app.run()
