import streamlit as st
import logging
import numpy as np
import math
import random
import connectors.openai_connector as Openai
import connectors.hsd_connector as HsdConnector
import modules.openai_handler as OpenaiHandler
import modules.hsd_handler as HsdHandler
import json
import os
import re
from openai import AzureOpenAI
import tiktoken
import httpx
import pandas as pd
from datetime import datetime
import traceback
# Initialize logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FCCBAnalyzer:
    """
    FCCB HSD Analyzer that extracts fuse information using HSD data and OpenAI analysis
    """
    def __init__(self):
        self.hsd_handler = HsdHandler.HSDHandler() if hasattr(HsdHandler, 'HSDHandler') else None
        self.openai_handler = OpenaiHandler.OpenAIHandler() if hasattr(OpenaiHandler, 'OpenAIHandler') else None
        self.openai_connector = Openai.OpenAIConnector() if hasattr(Openai, 'OpenAIConnector') else None
        
    def get_fccb_hsds(self, query_id=None, search_term="FCCB"):
        """
        Retrieve all FCCB related HSDs
        """
        try:
            if self.hsd_handler is None:
                return {"error": "HSD Handler not available"}
                
            # If query_id is provided, use it; otherwise search for FCCB HSDs
            if query_id:
                hsd_data = self.hsd_handler.fetch_query_data(query_id)
            else:
                # Search for FCCB related HSDs
                hsd_data = self.hsd_handler.search_hsds(search_term)
                
            return hsd_data
        except Exception as e:
            logger.error(f"Error getting FCCB HSDs: {e}")
            return {"error": str(e)}
    
    def extract_fuse_data_from_hsd(self, hsd_id):
        """
        Extract detailed fuse information from a specific HSD
        """
        try:
            if self.hsd_handler is None:
                return {"error": "HSD Handler not available"}
                
            # Get HSD details with specific fields for FCCB analysis
            # fields = [
            #     "id", "title", "description", "component", "die_name", 
            #     "fuse_name", "old_value", "new_value", "justification",
            #     "validation_status", "assignee", "status", "created_date"
            # ]
            
            # hsd_details = self.hsd_handler.hsd.get_hsd(hsd_id, fields)
            hsd_details = self.hsd_handler.hsd.get_hsd(hsd_id)
            # If HSD details are not found, return error
            if not hsd_details:
                return {"error": "HSD details not found"}
            return hsd_details
        except Exception as e:
            logger.error(f"Error extracting fuse data from HSD {hsd_id}: {e}")
            return {"error": str(e)}
    
    def analyze_fuse_changes_with_ai(self, hsd_data):
        """
        Use OpenAI to analyze HSD data and extract fuse information
        """
        try:
            if not hsd_data or "error" in hsd_data:
                return {"error": "Invalid HSD data provided"}
            
            # Prepare the system prompt for fuse analysis
            system_prompt = """You are an expert FCCB (Fuse Configuration Control Board) analyst with deep knowledge of Intel fuse configurations. 
            Your task is to analyze HSD data and extract the following information:
            1. Exact fuse name (usually in format like sv.socket0.io0.fuses.punit_fuses.fuse_name)
            2. Die/Component it belongs to (must be in format socket0.io0, socket0.io1, socket0.compute0, socket0.compute1, etc.)
            3. Old/existing fuse value (usually in hex format like 0x5)
            4. New/expected/requested fuse value (usually in hex format like 0x69)
            5. Reason for the change (bug fix, feature enabling, etc.)
            6. Validation impact
            
            IMPORTANT: For die_component field, always use the standardized socket notation format:
            - For IO dies: socket0.io0, socket0.io1, socket1.io0, etc.
            - For Compute dies: socket0.compute0, socket0.compute1, socket1.compute0, etc.
            - Extract this from the fuse path or HSD description/title
            
            Look for patterns like:
            - "Existing Fuse values" followed by fuse path and value
            - "Existing Fuse values" followed by fuse name and value
            - "Old Fuse Values" followed by fuse path and value
            - "Old Fuse Values" followed by fuse name and value
            - "Expected Fuse Values" followed by fuse path and value
            - "Expected Fuse Values" followed by fuse name and value
            - "new or requested Fuse Values" followed by fuse path and value
            - "new or requested Fuse Values" followed by fuse name and value
            - "fuses.punit_fuses.fuse_name = 0xValue"
            - Problem statements and functionality descriptions
            
            Please provide the response in a structured JSON format."""
            
            # Create the analysis prompt - handle both dict and string inputs
            if isinstance(hsd_data, dict):
                hsd_text = json.dumps(hsd_data, indent=2)
            else:
                hsd_text = str(hsd_data)
            
            user_prompt = f"""Please analyze this FCCB HSD data and extract fuse information:
            
            HSD Data:
            {hsd_text}
            
            Please provide the analysis in the following JSON format:
            {{
                "fuse_name": "exact fuse name (e.g., pcode_sst_bf_config_0_t_throttle)",
                "old_value": "current/existing fuse value (e.g., 0x5)",
                "new_value": "requested/expected new fuse value (e.g., 0x69)",
                "full_fuse_path": "complete fuse path (e.g., sv.socket0.io0.fuses.punit_fuses.pcode_sst_bf_config_0_t_throttle)",
                "die_component": "standardized socket notation (e.g., socket0.io0, socket0.io1, socket0.compute0, socket0.compute1)",
                "change_reason": "reason for the change (e.g., bug fix, feature enabling)",
                "validation_impact": "impact on validation and testing",
                "functionality": "what this fuse controls or affects",
                "confidence_score": "0.0 to 1.0 based on clarity of information"
            }}
            
            CRITICAL: For die_component field, ALWAYS use the exact socket notation format:
            - Extract from fuse path: if path contains "socket0.io0" → use "socket0.io0"
            - Extract from fuse path: if path contains "socket0.compute0" → use "socket0.compute0"
            - Look in title/description for terms like "IO-DIE", "COMPUTE-DIE", "XCC", "IOD"
            - Map to standardized format: IO die → socket0.io0, Compute die → socket0.compute0
            
            Look specifically for:
            - Fuse paths starting with "sv.socket" (extract socket notation from path)
            - "Existing Fuse values" and "Expected Fuse Values" sections
            - "Old Fuse values" and "new Fuse Values or requested Fuse Values" sections
            - Hex values or decimal values for the fuses
            - Problem statements and functionality descriptions
            - Die/component information in the title and description (socket0.io0, socket0.io1, socket0.compute0, socket0.compute1 etc)
            - Component names like punit, pcode, uncore, core, media, SOC, memory, CXL, PCIE etc"""
            
            # Use OpenAI to analyze
            if self.openai_connector:
                response = self.openai_connector.run_prompt(
                    [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                )
                
                # Handle the response from OpenAI connector
                if isinstance(response, dict) and "response" in response:
                    # Extract the actual response text
                    response_text = response["response"]
                elif isinstance(response, dict):
                    # If it's already a structured response, return it
                    return response
                else:
                    response_text = str(response)
                
                # Now try to parse the response text as JSON
                try:
                    result = json.loads(response_text)
                    return result
                except json.JSONDecodeError:
                    # If not valid JSON, return as text with structured format
                    return {
                        "analysis": response_text, 
                        "format": "text",
                        "raw_response": response
                    }
            else:
                return {"error": "OpenAI connector not available"}
                
        except Exception as e:
            logger.error(f"Error in AI analysis: {e}")
            return {"error": str(e)}
    
    def process_multiple_fccb_hsds(self, hsd_list):
        """
        Process multiple FCCB HSDs and extract fuse information from all
        """
        results = []
        
        for hsd_id in hsd_list:
            try:
                # Get HSD data
                hsd_data = self.extract_fuse_data_from_hsd(hsd_id)
                
                # Analyze with AI
                ai_analysis = self.analyze_fuse_changes_with_ai(hsd_data)
                
                # Combine results
                result = {
                    "hsd_id": hsd_id,
                    "hsd_data": hsd_data,
                    "ai_analysis": ai_analysis,
                    "processed_at": datetime.now().isoformat()
                }
                
                results.append(result)
                
            except Exception as e:
                logger.error(f"Error processing HSD {hsd_id}: {e}")
                results.append({
                    "hsd_id": hsd_id,
                    "error": str(e),
                    "processed_at": datetime.now().isoformat()
                })
        
        return results

def parse_ai_analysis(ai_analysis):
    """
    Parse AI analysis response which may be in different formats
    """
    if isinstance(ai_analysis, dict):
        # If it's already a dict, check for different response formats
        if "analysis" in ai_analysis and isinstance(ai_analysis["analysis"], str):
            # Extract JSON from markdown-wrapped string
            analysis_text = ai_analysis["analysis"]
            # Remove markdown code blocks if present
            if "```json" in analysis_text:
                # Extract JSON content between ```json and ```
                start = analysis_text.find("```json") + 7
                end = analysis_text.rfind("```")
                json_text = analysis_text[start:end].strip()
            else:
                json_text = analysis_text
            
            try:
                return json.loads(json_text)
            except json.JSONDecodeError:
                return {"error": "Failed to parse JSON from analysis"}
        
        elif "analysis" in ai_analysis and isinstance(ai_analysis["analysis"], dict):
            return ai_analysis["analysis"]
        else:
            # Return as-is if it's already in the expected format
            return ai_analysis
    
    return {"error": "Invalid AI analysis format"}

def fccb_analysis_app():
    """
    Main Streamlit app for FCCB HSD Analysis
    """
    st.title('🔧 FCCB HSD Analysis Tool')
    st.markdown("Analyze FCCB HSDs to extract fuse information including names, dies, old/new values")
    
    # Initialize the analyzer
    if 'fccb_analyzer' not in st.session_state:
        st.session_state.fccb_analyzer = FCCBAnalyzer()
    
    analyzer = st.session_state.fccb_analyzer
    
    # Sidebar for input options
    with st.sidebar:
        st.header("Analysis Options")
        
        analysis_type = st.radio(
            "Choose Analysis Type:",
            ["Single HSD", "Multiple HSDs", "Query Search", "Bulk Analysis"]
        )
        
        st.divider()
        
        if analysis_type == "Single HSD":
            hsd_id = st.text_input("Enter HSD ID:", placeholder="e.g., 1234567890")
            analyze_single = st.button("Analyze HSD", type="primary")
            
        elif analysis_type == "Multiple HSDs":
            hsd_ids_text = st.text_area(
                "Enter HSD IDs (one per line):", 
                placeholder="1234567890\n1234567891\n1234567892"
            )
            analyze_multiple = st.button("Analyze Multiple HSDs", type="primary")
            
        elif analysis_type == "Query Search":
            query_id = st.text_input("Enter Query ID:", placeholder="Query ID for FCCB HSDs")
            search_term = st.text_input("Search Term:", value="FCCB", placeholder="Search term")
            analyze_query = st.button("Search & Analyze", type="primary")
            
        elif analysis_type == "Bulk Analysis":
            uploaded_file = st.file_uploader("Upload CSV with HSD IDs", type=['csv'])
            analyze_bulk = st.button("Analyze from File", type="primary")
    
    # Main content area
    if analysis_type == "Single HSD" and 'analyze_single' in locals() and analyze_single:
        if hsd_id:
            with st.spinner(f"Analyzing HSD {hsd_id}..."):
                # Extract HSD data
                # hsd_data = analyzer.extract_fuse_data_from_hsd(hsd_id)
                # logger.info(f"Extracted HSD data: {hsd_data} \n\n")
                # # Analyze with AI
                # ai_analysis = analyzer.analyze_fuse_changes_with_ai(hsd_data)

                # logger.info(f"AI Analysis results: {ai_analysis}")
                # # Display results
                # display_fccb_analysis_results(hsd_id, hsd_data, ai_analysis)
                results = analyzer.process_multiple_fccb_hsds([hsd_id])
                display_multiple_results(results)
        else:
            st.warning("Please enter an HSD ID")
    
    elif analysis_type == "Multiple HSDs" and 'analyze_multiple' in locals() and analyze_multiple:
        if hsd_ids_text.strip():
            hsd_ids = [hsd_id.strip() for hsd_id in hsd_ids_text.split('\n') if hsd_id.strip()]
            
            if hsd_ids:
                with st.spinner(f"Analyzing {len(hsd_ids)} HSDs..."):
                    results = analyzer.process_multiple_fccb_hsds(hsd_ids)
                    display_multiple_results(results)
            else:
                st.warning("Please enter at least one HSD ID")
        else:
            st.warning("Please enter HSD IDs")
    
    elif analysis_type == "Query Search" and 'analyze_query' in locals() and analyze_query:
        with st.spinner("Searching and analyzing FCCB HSDs..."):
            fccb_data = analyzer.get_fccb_hsds(query_id, search_term)
            
            if "error" not in fccb_data:
                st.success(f"Found FCCB data")
                display_query_results(fccb_data)
            else:
                st.error(f"Error: {fccb_data['error']}")
    
    # Add help section
    with st.expander("ℹ️ How to use this tool"):
        st.markdown("""
        **FCCB HSD Analysis Tool Usage:**
        
        1. **Single HSD**: Enter one HSD ID to get detailed fuse analysis
        2. **Multiple HSDs**: Enter multiple HSD IDs (one per line) for batch analysis
        3. **Query Search**: Use HSD query ID or search term to find FCCB HSDs
        4. **Bulk Analysis**: Upload a CSV file with HSD IDs for large-scale analysis
        
        **What this tool extracts:**
        - Exact fuse names
        - Die/Component information
        - Old fuse values
        - New requested values
        - Change justification
        - Validation impact
        """)

def display_fccb_analysis_results(hsd_id, hsd_data, ai_analysis):
    """
    Display the analysis results for a single FCCB HSD
    """
    st.header(f"📊 Analysis Results for HSD: {hsd_id}")
    
    # Create tabs for different views
    tab1, tab2 = st.tabs(["🤖 AI Analysis", "📝 Raw HSD Data"])
    
    with tab1:
        st.subheader("AI Analysis Results")
        if isinstance(ai_analysis, dict) and "error" not in ai_analysis:
            st.json(ai_analysis)
        else:
            st.error(f"AI Analysis Error: {ai_analysis.get('error', 'Unknown error')}")
    
    with tab2:
        st.subheader("Raw HSD Data")
        if isinstance(hsd_data, dict) and "error" not in hsd_data:
            st.json(hsd_data)
        else:
            st.error(f"HSD Data Error: {hsd_data.get('error', 'Unknown error')}")

def display_multiple_results(results):
    """
    Display results for multiple HSDs
    """
    st.header(f"📊 Multiple HSD Analysis Results ({len(results)} HSDs)")
    try:
        # Create summary table
        summary_data = []
        for result in results:
            hsd_id = result.get("hsd_id", "Unknown")
            logger.info(f"Processing HSD {hsd_id}")
            if "error" in result:
                summary_data.append({
                    "HSD ID": hsd_id,
                    "Fuse Name": "Error",
                    "Die/Component": "Error",
                    "Old Value": "Error",
                    "New Value": "Error",
                    "Status": f"Error: {result['error']}"
                })
            else:
                ai_analysis = result.get("ai_analysis", {})
                # Parse the AI analysis to extract actual data
                parsed_analysis = parse_ai_analysis(ai_analysis)

                # logger.info(f"Processing HSD {hsd_id} with AI analysis: {ai_analysis}")
                # logger.info(f"\n Parsed analysis: {parsed_analysis}")
                # st.write(f"parsed: {parsed_analysis}")
                summary_data.append({
                    "HSD ID": hsd_id,
                    "Fuse Name": parsed_analysis.get("fuse_name", "Not found"),
                    "Die/Component": parsed_analysis.get("die_component", "Not found"),
                    "Old Value": parsed_analysis.get("old_value", "Not found"),
                    "New Value": parsed_analysis.get("new_value", "Not found"),
                    "Status": "Success" if "error" not in parsed_analysis else "Parse Error"
                })

        
        # Display summary table
        df = pd.DataFrame(summary_data)
        st.dataframe(df, use_container_width=True)

        # Download results
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download Results as CSV",
            data=csv,
            file_name=f"fccb_analysis_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

        # Detailed results in expander
        with st.expander("View Detailed Results"):
            for i, result in enumerate(results):
                st.subheader(f"HSD {result.get('hsd_id', f'#{i+1}')}")
                st.json(result)
    except Exception as e:
        st.error(f"Error displaying results: {e}")
        logger.error(f"Error in displaying multiple results: {e}")
        logger.error(f"traceback: {traceback.format_exc()}")

def display_query_results(fccb_data):
    """
    Display results from query search
    """
    st.header("🔍 Query Search Results")
    st.json(fccb_data)


def app():
    """
    Main app function called by the multiapp framework
    """
    logger.info("FCCB HSD Analysis app started")
    
    try:
        fccb_analysis_app()
    except Exception as e:
        st.error(f"Error running FCCB Analysis app: {e}")
        logger.error(f"Error in FCCB Analysis app: {e}")


# Legacy function for compatibility
def analyze_hsd_with_ai(hsd_data, analysis_type="summary"):
    """Legacy function for backward compatibility"""
    try:
        analyzer = FCCBAnalyzer()
        return analyzer.analyze_fuse_changes_with_ai(hsd_data)
    except Exception as e:
        return f"Analysis failed: {str(e)}"

