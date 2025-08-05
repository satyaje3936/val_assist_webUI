import streamlit as st
import pandas as pd
import json
import os
import sys
from datetime import datetime
from pathlib import Path
import time

# Add the parent directory to the path to import the original classes
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the classes and functions from the original script
try:
    from FCCB_HSD_Query_Summary import (
        HsdConnector, 
        OpenAIConnector, 
        convert_hsd_data_to_excel, 
        convert_ai_response_to_excel, 
        parse_hsd_summary_format,
        parse_fccb_json_to_excel,
        get_log_file_path
    )
except ImportError as e:
    st.error(f"Failed to import required modules: {e}")
    st.stop()

def app():
    st.title("🔍 FCCB HSD Query Summary & Analysis")
    st.markdown("Analyze FCCB HSDs data with AI-powered insights")

    # Sidebar for configuration
    st.sidebar.header("Configuration")
    
    # Input method selection
    input_method = st.sidebar.radio(
        "Select Input Method:",
        ["Query ID", "Single HSD ID"]
    )
    
    # Main input fields
    if input_method == "Query ID":
        query_id = st.text_input(
            "Enter Query ID:", 
            help="Enter the HSD query ID to fetch multiple HSDs"
        )
        hsd_id = None
        batch_size = st.sidebar.slider("Batch Size", min_value=1, max_value=10, value=3)
    else:
        hsd_id = st.text_input(
            "Enter HSD ID:", 
            help="Enter a single HSD ID for analysis"
        )
        query_id = None
        batch_size = None
    
    # Prompt configuration
    st.subheader("Analysis Configuration")
    
    # User prompt input
    user_prompt_method = st.radio(
        "User Prompt Method:",
        ["Enter text directly", "Upload text file"]
    )
    
    user_prompt = ""
    if user_prompt_method == "Enter text directly":
        user_prompt = st.text_area(
            "Enter your analysis prompt:",
            height=150,
            placeholder="Enter the prompt for AI analysis..."
        )
    else:
        uploaded_prompt_file = st.file_uploader(
            "Upload prompt file (.txt)",
            type=['txt'],
            help="Upload a text file containing your analysis prompt"
        )
        if uploaded_prompt_file is not None:
            user_prompt = str(uploaded_prompt_file.read(), "utf-8")
            st.text_area("Uploaded prompt:", user_prompt, height=100, disabled=True)
    
    # Report formatting (optional)
    report_formatting = ""
    use_report_formatting = st.checkbox("Use custom report formatting")
    if use_report_formatting:
        report_formatting_method = st.radio(
            "Report Formatting Method:",
            ["Enter text directly", "Upload text file"]
        )
        
        if report_formatting_method == "Enter text directly":
            report_formatting = st.text_area(
                "Enter report formatting instructions:",
                height=100,
                placeholder="Enter formatting instructions..."
            )
        else:
            uploaded_format_file = st.file_uploader(
                "Upload formatting file (.txt)",
                type=['txt'],
                help="Upload a text file containing formatting instructions"
            )
            if uploaded_format_file is not None:
                report_formatting = str(uploaded_format_file.read(), "utf-8")
                st.text_area("Uploaded formatting:", report_formatting, height=100, disabled=True)
    
    # Output configuration
    st.sidebar.subheader("Output Options")
    output_format = st.sidebar.selectbox(
        "Output Format:",
        ["text", "html", "json"],
        help="Select the format for AI response"
    )
    
    # Excel options
    excel_options = st.sidebar.multiselect(
        "Excel Export Options:",
        ["HSD Data Excel", "AI Analysis Excel"],
        help="Select which Excel files to generate"
    )
    
    hsd_excel = "HSD Data Excel" in excel_options
    ai_excel = "AI Analysis Excel" in excel_options
    
    # Processing button
    if st.button("🚀 Start Analysis", type="primary"):
        # Validation
        if not (query_id or hsd_id):
            st.error("Please enter either a Query ID or HSD ID")
            return
        
        if not user_prompt.strip():
            st.error("Please provide a user prompt for analysis")
            return
        
        # Show processing status
        with st.spinner("Processing HSD data and generating analysis..."):
            try:
                # Initialize connectors
                hsd_connector = HsdConnector()
                openai_connector = OpenAIConnector()
                
                # Prepare the prompt
                if output_format == "text":
                    output_ext = "Report the output in text format."
                elif output_format == "html":
                    output_ext = "Report the output ONLY in nicely formatted list in HTML format. Do not provide any preamble text."
                elif output_format == "json":
                    output_ext = "Report the output ONLY in nicely formatted JSON. Do not provide any preamble text."
                
                final_prompt = user_prompt + "\n" + report_formatting + "\n" + output_ext
                
                system_prompt = """You are an expert FCCB (Fuse Configuration Control Board) analyst with deep knowledge of Intel fuse configurations. 
            Your task is to analyze HSD data and extract the following information:
            1. Exact fuse name (usually in format like sv.socket0.io0.fuses.punit_fuses.fuse_name)
            2. Die/Component it belongs to (must be in format socket0.io0, socket0.io1, socket0.compute0, socket0.compute1, etc.)
            3. Old/existing fuse value (usually in hex format like 0x5)
            4. New/expected/requested fuse value (usually in hex format like 0x69)
            5. Reason for the change (bug fix, feature enabling, etc.)
            6. Validation impact
            
            CRITICAL JSON FORMAT REQUIREMENTS:
            - Use EXACTLY "hsd_id" field name (NOT "id") 
            - Use EXACTLY "title" field name
            - Use EXACTLY "fuse_analysis" array field name
            - Follow the exact JSON structure as specified in the prompt
            
            CRITICAL DIE COMPONENT PARSING RULES:
            - For IO dies: socket0.io0, socket0.io1, socket1.io0, etc.
            - For Compute dies: socket0.compute0, socket0.compute1, socket1.compute0, etc.
            - Extract this from the fuse path or HSD description/title
            
            IMPORTANT DUAL DIE HANDLING:
            If the HSD title or description mentions BOTH dies (e.g., "CDIE and IO Die", "IO-Die and Compute", "[CDIE][IO Die]"), 
            you MUST create SEPARATE fuse analysis entries for EACH die type:
            - One entry with die_component: "socket0.compute0" (for CDIE/C-DIE/C DIE/cdie/compute die)
            - One entry with die_component: "socket0.io0" (for IO-DIE/IO die/iodie/IO_DIE)
            - Both entries should have the same fuse name, values, and analysis but different die_component values
            
            DIE TYPE DETECTION PATTERNS:
            - CDIE patterns: "CDIE", "C-DIE", "C DIE", "cdie", "Compute die", "compute die", "HCC", "XCC"
            - IO Die patterns: "IO Die", "IO-Die", "IO_DIE", "iodie", "io die", "I/O die"
            - When you see patterns like "[CDIE][IO Die]" or "CDIE and IO Die" - create entries for BOTH
            
            CRITICAL RULE FOR REJECTED HSDs: If any HSD has status "rejected", still include it in the analysis but:
            - Keep the HSD ID in the response using "hsd_id" field
            - Set all analysis fields (fuse_name, old_value, new_value, die_component, change_reason, validation_impact, functionality) to "NA"
            - Add confidence_score: 0.0
            - Add a note indicating the HSD is rejected
            
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
            
            Please provide the response in a structured JSON format using EXACTLY these field names:
            - "hsd_id" (NOT "id")
            - "title" 
            - "fuse_analysis"
            
            Always include ALL HSDs regardless of their status.
            
            IMPORTANT: Provide ONLY valid JSON without any markdown formatting, comments, or additional text.
            Do not wrap the JSON in ```json code blocks.
            Do not include any // comments or /* */ comments in the JSON.
            Ensure all JSON syntax is correct with proper commas and brackets."""
                
                if query_id:
                    # Process query ID
                    st.info(f"Fetching HSD IDs from query: {query_id}")
                    hsd_ids = hsd_connector.fetch_hsd_ids_from_query(query_id)
                    
                    if not hsd_ids:
                        st.error("Failed to fetch HSD IDs from the query")
                        return
                    
                    st.success(f"Found {len(hsd_ids)} HSDs in query")
                    
                    # Process in batches
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    batch_files = hsd_connector.get_multiple_hsd_data_in_batch(hsd_ids, batch_size=batch_size)
                    all_responses = []
                    
                    for batch_num, batch_file in enumerate(batch_files, 1):
                        progress = batch_num / len(batch_files)
                        progress_bar.progress(progress)
                        status_text.text(f"Processing Batch {batch_num}/{len(batch_files)} with OpenAI...")
                        
                        try:
                            res = openai_connector.run_prompt_with_json(batch_file, system_prompt, final_prompt)
                            
                            # Create output filename for this batch
                            base_filename = Path(batch_file).stem
                            timestamp = base_filename.split('_')[-1]
                            new_base_filename = '_'.join(base_filename.split('_')[:-1]) + '_gpt_output_' + timestamp
                            
                            # Determine file extension
                            extension = ".txt" if output_format == "text" else ".html" if output_format == "html" else ".json"
                            batch_output_filename = get_log_file_path(new_base_filename + extension)
                            
                            # Save batch response
                            with open(batch_output_filename, "w", encoding='utf-8') as file:
                                file.write(res['response'])
                            
                            all_responses.append({
                                'batch_num': batch_num,
                                'batch_file': batch_file,
                                'output_file': str(batch_output_filename),
                                'response': res['response']
                            })
                            
                            # Convert to Excel per batch if --hsd_excel is specified
                            if hsd_excel:
                                hsd_excel_filename = get_log_file_path(f"{Path(batch_file).stem}.xlsx")
                                convert_hsd_data_to_excel(batch_file, str(hsd_excel_filename))
                        
                        except Exception as e:
                            st.error(f"Error processing batch {batch_num}: {e}")
                            all_responses.append({
                                'batch_num': batch_num,
                                'batch_file': batch_file,
                                'error': str(e)
                            })
                    
                    progress_bar.progress(1.0)
                    status_text.text("Processing complete!")
                    
                    successful_batches = [r for r in all_responses if 'error' not in r]
                    failed_batches = [r for r in all_responses if 'error' in r]
                    
                    # Create consolidated Excel files
                    consolidated_files = {}
                    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                    
                    if hsd_excel:
                        st.info("Creating consolidated HSD Excel file...")
                        consolidated_hsd_excel = get_log_file_path(f"consolidated_hsd_data_{query_id}_{timestamp}.xlsx")
                        
                        # Combine all HSD data from successful batches
                        all_hsd_data = {"data": []}
                        for batch_file in batch_files:
                            try:
                                with open(batch_file, 'r', encoding='utf-8') as f:
                                    batch_data = json.load(f)
                                    if "data" in batch_data and isinstance(batch_data["data"], list):
                                        all_hsd_data["data"].extend(batch_data["data"])
                            except Exception as e:
                                st.warning(f"Could not read batch file {batch_file}: {e}")
                        
                        # Save consolidated HSD data to temporary JSON and convert to Excel
                        temp_hsd_json = get_log_file_path(f"temp_consolidated_hsd_{timestamp}.json")
                        with open(temp_hsd_json, 'w', encoding='utf-8') as f:
                            json.dump(all_hsd_data, f, indent=4, ensure_ascii=False)
                        
                        convert_hsd_data_to_excel(temp_hsd_json, consolidated_hsd_excel)
                        os.remove(temp_hsd_json)  # Clean up temporary file
                        consolidated_files['hsd_excel'] = consolidated_hsd_excel
                    
                    if ai_excel:
                        st.info("Creating consolidated AI Analysis Excel file...")
                        consolidated_ai_excel = get_log_file_path(f"consolidated_ai_responses_{query_id}_{timestamp}.xlsx")
                        
                        # Add debugging information to show parsing results
                        st.subheader("📊 AI Response Parsing Debug Information")
                        total_hsds_parsed = 0
                        
                        for i, response in enumerate(successful_batches, 1):
                            with st.expander(f"Batch {i} Parsing Results"):
                                try:
                                    # Test parse the response to show what HSDs are found
                                    parsed_df = parse_hsd_summary_format(response['response'])
                                    if parsed_df is not None and not parsed_df.empty:
                                        st.success(f"✅ Successfully parsed {len(parsed_df)} HSDs from Batch {i}")
                                        st.dataframe(parsed_df[['HSD ID']], use_container_width=True)
                                        total_hsds_parsed += len(parsed_df)
                                    else:
                                        st.warning(f"⚠️ No HSDs parsed from Batch {i}")
                                        st.text_area(f"Response preview (Batch {i}):", response['response'][:300] + "...", height=100)
                                except Exception as e:
                                    st.error(f"❌ Error parsing Batch {i}: {e}")
                        
                        st.info(f"📈 Total HSDs parsed across all batches: {total_hsds_parsed} out of {len(hsd_ids)} original HSDs")
                        
                        if total_hsds_parsed < len(hsd_ids):
                            st.warning(f"⚠️ Missing {len(hsd_ids) - total_hsds_parsed} HSDs in AI analysis. Check batch responses for formatting issues.")
                        
                        parse_fccb_json_to_excel(successful_batches, consolidated_ai_excel)
                        #create_consolidated_hsd_summary_excel(successful_batches, consolidated_ai_excel)
                        consolidated_files['ai_excel'] = consolidated_ai_excel
                    
                    # Display results
                    st.success("🎉 Analysis Complete!")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Total HSDs", len(hsd_ids))
                        st.metric("Successful Batches", len(successful_batches))
                    with col2:
                        st.metric("Total Batches", len(batch_files))
                        st.metric("Failed Batches", len(failed_batches))
                    
                    # Show batch results
                    st.subheader("Batch Processing Results")
                    for response in all_responses:
                        if 'error' not in response:
                            with st.expander(f"✅ Batch {response['batch_num']} - Success"):
                                st.text(f"Output file: {response['output_file']}")
                                st.text_area("Response Preview:", response['response'][:500] + "..." if len(response['response']) > 500 else response['response'], height=200)
                        else:
                            with st.expander(f"❌ Batch {response['batch_num']} - Failed"):
                                st.error(f"Error: {response['error']}")
                    
                    # Show download links for consolidated files
                    if consolidated_files:
                        st.subheader("📊 Generated Files")
                        for file_type, file_path in consolidated_files.items():
                            if os.path.exists(file_path):
                                with open(file_path, 'rb') as f:
                                    file_data = f.read()
                                file_name = Path(file_path).name
                                st.download_button(
                                    label=f"📥 Download {file_type.replace('_', ' ').title()}",
                                    data=file_data,
                                    file_name=file_name,
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                )
                
                elif hsd_id:
                    # Process single HSD ID
                    st.info(f"Fetching data for HSD ID: {hsd_id}")
                    hsd_query_data_file = hsd_connector.get_hsd_data_in_file(hsd_id)
                    
                    if hsd_query_data_file is None:
                        st.error("Failed to fetch HSD data")
                        return
                    
                    st.success("HSD data fetched successfully")
                    
                    # Process with OpenAI
                    st.info("Analyzing with AI...")
                    res = openai_connector.run_prompt_with_json(hsd_query_data_file, system_prompt, final_prompt)
                    
                    # Create output filename
                    base_filename = Path(hsd_query_data_file).stem
                    timestamp = base_filename.split('_')[-1]
                    new_base_filename = '_'.join(base_filename.split('_')[:-1]) + '_gpt_output_' + timestamp
                    
                    extension = ".txt" if output_format == "text" else ".html" if output_format == "html" else ".json"
                    openai_output_filename = get_log_file_path(new_base_filename + extension)
                    
                    with open(openai_output_filename, "w", encoding='utf-8') as file:
                        file.write(res['response'])
                    
                    # Create Excel files if requested
                    excel_files = {}
                    if hsd_excel:
                        hsd_excel_filename = get_log_file_path(f"{Path(hsd_query_data_file).stem}.xlsx")
                        convert_hsd_data_to_excel(hsd_query_data_file, str(hsd_excel_filename))
                        excel_files['hsd_excel'] = hsd_excel_filename
                    
                    if ai_excel:
                        ai_excel_filename = get_log_file_path(f"consolidated_ai_responses_{hsd_id}_{timestamp}.xlsx")
                        
                        # Add debugging information for single HSD parsing
                        st.subheader("📊 AI Response Parsing Debug Information")
                        try:
                            parsed_df = parse_hsd_summary_format(res['response'])
                            if parsed_df is not None and not parsed_df.empty:
                                st.success(f"✅ Successfully parsed {len(parsed_df)} HSD from AI response")
                                st.dataframe(parsed_df, use_container_width=True)
                            else:
                                st.warning("⚠️ No HSD data parsed from AI response")
                                st.text_area("Response preview:", res['response'][:300] + "...", height=100)
                        except Exception as e:
                            st.error(f"❌ Error parsing AI response: {e}")
                        
                        convert_ai_response_to_excel(str(openai_output_filename), str(ai_excel_filename))
                        excel_files['ai_excel'] = ai_excel_filename
                    
                    # Display results
                    st.success("🎉 Analysis Complete!")
                    
                    st.subheader("AI Analysis Results")
                    if output_format == "html":
                        st.markdown(res['response'], unsafe_allow_html=True)
                    elif output_format == "json":
                        try:
                            json_data = json.loads(res['response'])
                            st.json(json_data)
                        except json.JSONDecodeError:
                            st.text_area("AI Response:", res['response'], height=400)
                    else:
                        st.text_area("AI Response:", res['response'], height=400)
                    
                    # Download buttons
                    st.subheader("📥 Download Files")
                    
                    # Download AI response
                    with open(openai_output_filename, 'r', encoding='utf-8') as f:
                        response_data = f.read()
                    st.download_button(
                        label="📄 Download AI Response",
                        data=response_data,
                        file_name=Path(openai_output_filename).name,
                        mime="text/plain"
                    )
                    
                    # Download Excel files
                    for file_type, file_path in excel_files.items():
                        if os.path.exists(file_path):
                            with open(file_path, 'rb') as f:
                                file_data = f.read()
                            file_name = Path(file_path).name
                            st.download_button(
                                label=f"📊 Download {file_type.replace('_', ' ').title()}",
                                data=file_data,
                                file_name=file_name,
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
            
            except Exception as e:
                st.error(f"An error occurred during processing: {e}")
                st.error("Please check your inputs and try again.")
    
    # Information section
    with st.expander("ℹ️ Help & Information"):
        st.markdown("""
        ### How to use this tool:
        
        1. **Choose Input Method:**
           - **Query ID**: Process multiple HSDs from a query (recommended for bulk analysis)
           - **Single HSD ID**: Analyze a specific HSD
        
        2. **Configure Analysis:**
           - Enter your analysis prompt (what you want the AI to focus on)
           - Optionally add custom report formatting instructions
           - Choose output format (text, HTML, or JSON)
        
        3. **Select Excel Options:**
           - **HSD Data Excel**: Raw HSD data in Excel format
           - **AI Analysis Excel**: Structured AI analysis results
        
        4. **Start Analysis:**
           - Click "Start Analysis" to begin processing
           - Monitor progress and view results
        
        ### Features:
        - ✅ Batch processing for large queries
        - ✅ AI-powered analysis with professional insights
        - ✅ Multiple output formats
        - ✅ Excel export capabilities
        - ✅ Download generated files
        
        ### Requirements:
        - Valid HSD query ID or HSD ID
        - OpenAI API access configured
        - Kerberos authentication for HSD API access
        """)

if __name__ == "__main__":
    app()
