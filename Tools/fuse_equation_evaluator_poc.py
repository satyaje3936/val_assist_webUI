#!/usr/bin/env python3
"""
POC: Excel Fuse Equation Evaluator
Reads Excel file and evaluates fuse equations based on LIRA attributes and values
"""

import pandas as pd
import re
import os
import sys
import json
import time
import argparse
import requests
import urllib3
import http.client
import traceback
from datetime import datetime
from typing import Dict, Any, List, Tuple
from pathlib import Path
from requests_kerberos import HTTPKerberosAuth

# Suppress SSL warnings for internal Intel API calls
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import pandas as pd
import re

# Create fuse report directory function
def ensure_fuse_report_directory():
    """Create the fuse_report directory if it doesn't exist (relative to script location)"""
    # Get the directory where this script is located (Tools folder)
    script_dir = Path(__file__).parent
    # Create fuse_report folder inside the Tools directory
    fuse_report_dir = script_dir / "fuse_report_logs"
    fuse_report_dir.mkdir(parents=True, exist_ok=True)
    return fuse_report_dir

def get_fuse_report_file_path(filename):
    """Get the full path for a file in the fuse_report directory"""
    fuse_report_dir = ensure_fuse_report_directory()
    return fuse_report_dir / filename

def extract_hsd_id_from_string(hsd_info_string):
    """
    Extract HSD ID from a string containing HSD information.
    Looks for patterns like https://hsdes.intel.com/appstore/article/#/15016510719
    or standalone 10-11 digit numbers at the end of strings.
    
    Args:
        hsd_info_string (str): String containing HSD information
        
    Returns:
        str: HSD ID if found, None otherwise
    """
    if not hsd_info_string or str(hsd_info_string).strip().lower() in ['nan', 'none', '', 'n/a']:
        return None
    
    hsd_info_str = str(hsd_info_string).strip()
    
    # Pattern 1: Look for hsdes.intel.com URLs with HSD ID (highest priority)
    hsdes_pattern = r'https://hsdes\.intel\.com/appstore/article/#/(\d{10,11})'
    match = re.search(hsdes_pattern, hsd_info_str)
    if match:
        return match.group(1)
    
    # Pattern 2: Look for exactly 10-11 digit numbers (valid HSD ID range)
    hsd_pattern = r'\b(\d{10,11})\b'
    matches = re.findall(hsd_pattern, hsd_info_str)
    
    if matches:
        # Filter to only include numbers that are exactly 10 or 11 digits
        valid_hsds = [match for match in matches if len(match) in [10, 11]]
        if valid_hsds:
            # Return the last valid HSD ID found (most likely to be the actual HSD ID)
            return valid_hsds[-1]
    
    return None

# Add the parent directory to sys.path to import connectors
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Import OpenAI connector
try:
    from connectors.openai_connector import OpenAIConnector
    OPENAI_AVAILABLE = True
    print("✅ OpenAI connector found and imported successfully")
except ImportError as e:
    try:
        # Try alternative import path
        sys.path.append(os.path.join(parent_dir, 'connectors'))
        from connectors.openai_connector import OpenAIConnector
        OPENAI_AVAILABLE = True
        print("✅ OpenAI connector found via alternative path")
    except ImportError:
        OPENAI_AVAILABLE = False
        print(f"⚠️ OpenAI connector not found. Error: {e}")
        print(f"🔍 Searched paths:")
        print(f"   - {os.path.join(parent_dir, 'connectors', 'openai_connector.py')}")
        print(f"   - Current working directory: {os.getcwd()}")
        print(f"   - Python path: {sys.path[-3:]}")  # Show last 3 paths





class HsdConnector:
    def _get_response(self, req, headers):
        """
        def _get_response(self, req, headers):
        This function sends a GET request to a specified URL and returns the response data.

        Parameters:
        req (str): The URL to send the GET request to.

        Returns:
        dict: The response data parsed as JSON.

        Raises:
        HTTPError: If the GET request is not successful (i.e., if the response status code is not 200).
        Exception: If there is an error when trying to parse the response data as JSON.
    """
        # Send a GET request to the specified URL (req) with the provided headers
        response = requests.get(req, auth=HTTPKerberosAuth(), verify=False, headers=headers)
        # If the response is successful (status code 200)
        if response.ok:
            try:
                # Try to parse the response data as JSON
                response_data = response.json()
                # Return the parsed data
                return response_data
            except Exception as e:
                # If an error occurs during parsing, raise the exception
                raise e
        else:
            # If the response is not successful, raise an HTTPError for the given status code
            response.raise_for_status()

    def printing_data_dump_on_userprompt(self, full_response_data, hsd_query_data_file):
        if "data" in full_response_data and isinstance(full_response_data["data"], list) and full_response_data["data"]:
            field_keys = full_response_data["data"][0].keys()
            print(f"The fields that we are writing into the {hsd_query_data_file} file are: {', '.join(field_keys)}")
   
    def get_hsd(self, hsd_id, fields=None):
        """
        Fetches detailed information about an HSD page using its ID. The method sends a GET request to the HSD API and
        retrieves the data associated with the given ID. The data is returned as a dictionary.
        Note: The HSD API requires Kerberos authentication. Meaning it can only be executed locally and not over cloud.
        Parameters:
        id (str): The ID of the HSD page to fetch information for.
        fields (List<str>): fields to include in the response, list of strings (optional). If not defined, returns all fields.
        Returns:
        dict: A dictionary containing detailed information about the HSD page. The dictionary includes the data
        associated with the given ID. If the ID does not exist or the request fails, the method raises an exception.
        Raises:
        requests.exceptions.HTTPError: If the HTTP request encounters an error or if the response status code is not 200 OK.
        urllib3.exceptions.MaxRetryError: If the HSD could not be found and reached MAX retries count (10)
        requests.exceptions.ProxyError: Problem with proxy settings
        http.client.RemoteDisconnected: During the query the remote was disconnected
        https://hsdes-api.intel.com/rest/article/{id}?fields={field1}%2C%20{field1}%2C%20{field1}...
        :param hsd_id: the hsd id
        :param fields: list of field names
        :return:json of all the fields returned from the hsd
        """
        if fields == "":  # Backwards compatibility
            fields = None
        assert fields is None or (len(fields) > 0 and type(fields) != str and all([type(f) == str for f in fields])), \
            "fields must be None or a list\\iterator of strings. Got %s." % (repr(fields),)
        fields = ["id","title", "description", "status", "comments"]
        
        retry = 10
        while (retry > 0):
            try:
                req = "https://hsdes-api.intel.com/rest/article/" + str(hsd_id)
                if fields is not None:
                    req += "?fields=" + "%2C%20".join(fields)
                headers = {'Content-type': 'application/json'}
                # print req
                response_data = self._get_response(req, headers)
                if "data" in response_data:
                    return response_data["data"][0]
                else:
                    raise Exception('Could not find "data" in response...')
            except urllib3.exceptions.MaxRetryError:
                print('Got "urllib3.exceptions.MaxRetryError" exception, retrying {} more attempts'.format(retry - 1))
                retry -= 1
            except requests.exceptions.ProxyError:
                print('Got "requests.exceptions.ProxyError" exception, retrying {} more attempts'.format(retry - 1))
                retry -= 1
            except http.client.RemoteDisconnected:
                print('Got "http.client.RemoteDisconnected" exception, retrying {} more attempts'.format(retry - 1))
                retry -= 1
            except Exception as e:
                print(
                    'Got unknown exception: {}, retrying {} more attempts'.format(traceback.format_exc(), (retry - 1)))
                retry -= 1

    def get_multiple_hsd_data_in_batch(self, hsd_ids, batch_size=8, fields=None):
        """
        Fetches detailed information for multiple HSD IDs in batches and saves each batch to separate JSON files.
        This helps avoid token limits when processing large numbers of HSDs.
        
        Parameters:
        hsd_ids (list): List of HSD IDs to fetch information for.
        batch_size (int): Number of HSDs to process in each batch (default: 10)
        fields (List<str>): fields to include in the response, list of strings (optional).
        
        Returns:
        list: List of JSON file paths containing batch data
        """
        # fields = ["id","title", "description", "status", "comments","forum_notes"]
        fields = ["id","title", "description", "status", "comments"]
        
        if not hsd_ids or not isinstance(hsd_ids, list):
            raise ValueError("hsd_ids must be a non-empty list")
        
        # Split HSDs into batches
        batches = [hsd_ids[i:i + batch_size] for i in range(0, len(hsd_ids), batch_size)]
        batch_files = []
        
        print(f"📊 Processing {len(hsd_ids)} HSDs in {len(batches)} batches of {batch_size} HSDs each...")
        
        for batch_num, batch_hsd_ids in enumerate(batches, 1):
            print(f"\n🔄 Processing Batch {batch_num}/{len(batches)} ({len(batch_hsd_ids)} HSDs)...")
            
            # Generate timestamp and dynamic filename for this batch
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            batch_file = f"hsd_batch_{batch_num}_of_{len(batches)}_{len(batch_hsd_ids)}hsds_{timestamp}.json"
            # Get full path in fuse_report directory
            full_batch_path = get_fuse_report_file_path(batch_file)
            
            # Initialize batch data structure
            batch_data = {"data": []}
            successful_count = 0
            failed_count = 0
            
            for i, hsd_id in enumerate(batch_hsd_ids, 1):
                print(f"  Processing HSD {i}/{len(batch_hsd_ids)} in batch {batch_num}: {hsd_id}")
                retry = 10
                success = False
                
                while retry > 0 and not success:
                    try:
                        req = "https://hsdes-api.intel.com/rest/article/" + str(hsd_id)
                        if fields is not None:
                            req += "?fields=" + "%2C%20".join(fields)
                        headers = {'Content-type': 'application/json'}
                        
                        response_data = self._get_response(req, headers)
                        
                        if "data" in response_data:
                            if isinstance(response_data["data"], list):
                                batch_data["data"].extend(response_data["data"])
                            else:
                                batch_data["data"].append(response_data["data"])
                            successful_count += 1
                            success = True
                        else:
                            print(f"    ✗ No data found for HSD ID: {hsd_id}")
                            failed_count += 1
                            success = True
                            
                    except Exception as e:
                        print(f'    ⚠ Error for HSD {hsd_id}: {str(e)}, retrying {retry - 1} more attempts')
                        retry -= 1
                
                if not success:
                    print(f"    ✗ Failed to fetch data for HSD ID: {hsd_id} after all retries")
                    failed_count += 1
            
            # Save batch data to file
            with open(full_batch_path, 'w', encoding='utf-8') as f:
                json.dump(batch_data, f, indent=4, ensure_ascii=False)
            
            batch_files.append(str(full_batch_path))
            
            print(f"  ✅ Batch {batch_num} complete:")
            print(f"    • Successful: {successful_count}")
            print(f"    • Failed: {failed_count}")
            print(f"    • HSDs with content: {len(batch_data['data'])}")
            print(f"    • Saved to: '{full_batch_path}'")
        
        print(f"\n📊 All Batches Complete:")
        print(f"  • Total batches: {len(batches)}")
        print(f"  • Batch files created: {len(batch_files)}")
        
        return batch_files
    
    def get_hsd_data_in_file(self, hsd_id, fields=None):
        """
        Fetches detailed information about an HSD page using its ID. The method sends a GET request to the HSD API and
        retrieves the data associated with the given ID. The data is returned as a dictionary.
        Note: The HSD API requires Kerberos authentication. Meaning it can only be executed locally and not over cloud.
        Parameters:
        id (str): The ID of the HSD page to fetch information for.
        fields (List<str>): fields to include in the response, list of strings (optional). If not defined, returns all fields.
        Returns:
        dict: A dictionary containing detailed information about the HSD page. The dictionary includes the data
        associated with the given ID. If the ID does not exist or the request fails, the method raises an exception.
        Raises:
        requests.exceptions.HTTPError: If the HTTP request encounters an error or if the response status code is not 200 OK.
        urllib3.exceptions.MaxRetryError: If the HSD could not be found and reached MAX retries count (10)
        requests.exceptions.ProxyError: Problem with proxy settings
        http.client.RemoteDisconnected: During the query the remote was disconnected
        https://hsdes-api.intel.com/rest/article/{id}?fields={field1}%2C%20{field1}%2C%20{field1}...
        :param hsd_id: the hsd id
        :param fields: list of field names
        :return:File name to json data  for all the fields returned from the hsd id
        """
        # FIXME (vbbhogad) THis is an ugly implementation rigt now where we dump the entire HSD data in dictionary to a file (which lingers around). This will need to eliminaited and fucntion shoudl only pass the JSON)
        # fields = ["id","title", "description", "subject", "owner", "status", "comments", "tenant", "bugeco.por", "component"]
        fields = ["id","title", "description", "status", "comments"]

        if fields == "":  # Backwards compatibility
            fields = None
        assert fields is None or (len(fields) > 0 and type(fields) != str and all([type(f) == str for f in fields])), \
            "fields must be None or a list\\iterator of strings. Got %s." % (repr(fields),)
        retry = 10
        while (retry > 0):
            try:
                req = "https://hsdes-api.intel.com/rest/article/" + str(hsd_id)
                if fields is not None:
                    req += "?fields=" + "%2C%20".join(fields)
                headers = {'Content-type': 'application/json'}
                # print req
                response_data = self._get_response(req, headers)
                if "data" in response_data:
                    #return response_data["data"][0]
                   # Generate the timestamp and dynamic filename
                   timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                   hsd_id_data_file = f"hsd_query_{hsd_id}_{timestamp}.json"
                   # Get full path in fuse_report directory
                   full_file_path = get_fuse_report_file_path(hsd_id_data_file)
                   with open(full_file_path, 'w', encoding='utf-8') as final_file:
                       json.dump(response_data, final_file, indent=4, ensure_ascii=False)
                       #print(f"Full JSON data has been saved to '{full_file_path}'\n")
                       return str(full_file_path)
                else:
                    raise Exception('Could not find "data" in response...')
            except urllib3.exceptions.MaxRetryError:
                print('Got "urllib3.exceptions.MaxRetryError" exception, retrying {} more attempts'.format(retry - 1))
                retry -= 1
            except requests.exceptions.ProxyError:
                print('Got "requests.exceptions.ProxyError" exception, retrying {} more attempts'.format(retry - 1))
                retry -= 1
            except http.client.RemoteDisconnected:
                print('Got "http.client.RemoteDisconnected" exception, retrying {} more attempts'.format(retry - 1))
                retry -= 1
            except Exception as e:
                print(
                    'Got unknown exception: {}, retrying {} more attempts'.format(traceback.format_exc(), (retry - 1)))
                retry -= 1

class FuseEquationEvaluator:
    """
    A class to evaluate fuse equations from Excel files using OpenAI
    """
    
    def __init__(self, excel_file_path: str):
        """
        Initialize the evaluator with Excel file path
        
        Args:
            excel_file_path (str): Path to the Excel file
        """
        self.excel_file_path = excel_file_path
        self.data = None
        self.results = []
        self.openai_connector = None
        
        # Initialize OpenAI connector if available
        if OPENAI_AVAILABLE:
            try:
                self.openai_connector = OpenAIConnector()
                print("✅ OpenAI connector initialized successfully")
            except Exception as e:
                print(f"⚠️ Failed to initialize OpenAI connector: {e}")
                self.openai_connector = None
        else:
            print("❌ OpenAI connector not available")
        
        # Fixed column names as specified for the new Excel structure
        self.column_names = {
            'line_number': 'Line_Number',
            'fuse_type': 'Fuse_Type',
            'fuse_name': 'Fuse_Name',
            'actual_value': 'Actual_Value_from_Report',
            'lira_attribute': 'LIRA Attributes', 
            'lira_value': 'LIRA Value',
            'attribute_count': 'Attribute_Count',
            'assigned_value': 'Assigned_Value',
            'equation': 'Fuse_Equation',
            'hsd_info': 'HSD_Info'
        }
        
    def load_excel_file(self, sheet_name: str = None) -> bool:
        """
        Load Excel file into pandas DataFrame
        
        Args:
            sheet_name (str): Name of the sheet to load (optional)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if sheet_name:
                self.data = pd.read_excel(self.excel_file_path, sheet_name=sheet_name)
            else:
                self.data = pd.read_excel(self.excel_file_path)
            
            print(f"✅ Successfully loaded Excel file: {self.excel_file_path}")
            print(f"📊 Data shape: {self.data.shape}")
            print(f"📋 Available columns: {list(self.data.columns)}")
            
            # Validate required columns
            missing_columns = []
            for col_key, col_name in self.column_names.items():
                if col_name not in self.data.columns:
                    missing_columns.append(col_name)
            
            if missing_columns:
                print(f"⚠️ Missing expected columns: {missing_columns}")
                print(f"📋 Please ensure your Excel file has these exact column names:")
                for col_name in self.column_names.values():
                    print(f"   • {col_name}")
                return False
            else:
                print("✅ All required columns found")
            
            return True
            
        except Exception as e:
            print(f"❌ Error loading Excel file: {e}")
            return False
    
    def evaluate_equation_with_openai(self, row_data: Dict[str, Any]) -> Tuple[Any, str, str]:
        """
        Evaluate fuse equation using OpenAI
        
        Args:
            row_data (Dict[str, Any]): Row data containing all column information
            
        Returns:
            Tuple[Any, str, str]: (result, explanation, status)
        """
        if not self.openai_connector:
            return "OpenAI not available", "OpenAI connector not initialized", "Error"
        
        # Extract row information using new column names
        fuse_type = row_data.get('Fuse_Type', 'Unknown')
        lira_attribute = row_data.get('LIRA Attributes', 'Unknown')
        lira_value = row_data.get('LIRA Value', 'Unknown')
        fuse_name = row_data.get('Fuse_Name', 'Unknown')
        actual_value = row_data.get('Actual_Value_from_Report', 'Unknown')
        hsd_info = row_data.get('HSD_Info', 'Unknown')
        equation = row_data.get('Fuse_Equation', 'Unknown')
        assigned_value = row_data.get('Assigned_Value', 'Unknown')
        attribute_count = row_data.get('Attribute_Count', 'Unknown')
        fusing_recipe = 1  # Placeholder, not used in current logic
        
        # Extract HSD ID from HSD Info and fetch HSD data
        hsd_data_file = None
        hsd_data = None
        hsd_id = extract_hsd_id_from_string(hsd_info)
        
        if hsd_id:
            # print(f"   🔍 Extracted HSD ID: {hsd_id} from HSD Info: {str(hsd_info)[:100]}...")
            print(f"   🔍 Extracted HSD ID: {hsd_id}")
            try:
                hsd_connector = HsdConnector()
                #hsd_data_file = hsd_connector.get_hsd_data_in_file(hsd_id)
                hsd_data = hsd_connector.get_hsd(hsd_id)
                if hsd_data:
                    print(f"   ✅ HSD data retrieved successfully")
                else:
                    print(f"   ❌ Failed to fetch HSD data for ID: {hsd_id}")
            except Exception as e:
                print(f"   ⚠️ Error fetching HSD data for ID {hsd_id}: {e}")
        else:
            print(f"   ⚠️ No HSD ID found in HSD Info: {str(hsd_info)[:100]}...")

        # if hsd_data_file:
        if hsd_data:
            # Process HSD data file

            # System prompt
            system_prompt_hsd = """You are a professional Intel HSD (Hardware Support Desk) analyst with extensive experience in analyzing semiconductor engineering issues, validation challenges, and hardware development processes.
            Your expertise includes:
            - Deep understanding of Intel SoC architectures, validation methodologies, and engineering workflows
            - Comprehensive knowledge of hardware development lifecycle, bug tracking, and issue resolution processes
            - Experience with multi-die systems, fuse configurations, power management, and silicon validation
            - Proficiency in analyzing technical documentation, engineering discussions, and project status updates

            Your task is to analyze the provided HSD data and provide a comprehensive professional analysis that includes:

            1. **EXECUTIVE SUMMARY**: 
               - Brief overview of the HSD issue in 2-3 sentences
               - Primary impact and criticality level
               - Current status and resolution timeline if available

            2. **TECHNICAL ANALYSIS**:
               - Detailed breakdown of the technical problem/request
               - Components, dies, or systems affected (compute die, IO die, memory, etc.)
               - Root cause analysis if provided in the HSD
               - Technical complexity and engineering challenges involved

            3. **PROGRESS & STATUS TRACKING**:
               - Latest updates and progress made (from comments, status changes, owner updates)
               - Key milestones achieved or missed
               - Current blockers or dependencies
               - Timeline and expected resolution dates

            4. **STAKEHOLDER IMPACT**:
               - Affected teams, validation engineers, and business units
               - Impact on project schedules, silicon validation, or product releases
               - Risk assessment and mitigation strategies mentioned

            5. **ACTION ITEMS & RECOMMENDATIONS**:
               - Outstanding action items and responsibilities
               - Recommended next steps based on the current state
               - Priority level and urgency indicators

            6. **HISTORICAL CONTEXT**:
               - How long the issue has been active
               - Evolution of the problem and solution approaches
               - Similar or related HSDs if referenced

            ANALYSIS GUIDELINES:
            - Focus on engineering substance and business impact
            - Identify patterns in comments that indicate progress or setbacks
            - Pay attention to ownership changes, status updates, and timeline shifts
            - Look for validation impact, testing implications, and cross-team dependencies
            - Highlight any compliance, security, or quality concerns
            - Extract quantitative data (dates, versions, test results) when available

            Please provide your analysis in a clear, professional format that would be suitable for engineering management review and decision-making."""

            user_action_prompt = '''Please analyze the HSD data and provide a concise summary.

            Provide your analysis in the following simple format:

            **HSD ID:** [Extract HSD ID]

            **Summary:** [Provide a clear and concise 2-3 line summary covering: the main issue/problem, current status/progress, and impact or next steps]

            **Instructions:**
            - Keep the summary to exactly in 5 lines maximum
            - First line: What is the main technical issue or request (give more insight or details)
            - Second line: Current status, progress, or resolution state  
            - Third line (if needed): Impact, timeline, or critical next steps
            - Focus on the most important information for quick understanding
            - Use clear, technical language suitable for engineering teams'''
            
            # Convert hsd_data dictionary to JSON string for OpenAI processing
            hsd_data_str = json.dumps(hsd_data, indent=2) if isinstance(hsd_data, dict) else str(hsd_data)
            
            # Process with OpenAI
            res = self.openai_connector.run_system_user_prompt(hsd_data_str, system_prompt_hsd, user_action_prompt)
            

            summary = self.extract_hsd_summary_from_response(res, hsd_id)
            print(f"   📄 HSD Summary: {summary}")
        else:
            summary = "NA"

        #Use AI to evaluate the fuse equation
        # Create detailed prompt for OpenAI
        prompt = f"""
        You are an expert fuse configuration evaluator. Please evaluate the following fuse equation and provide the calculated result.
        
        FUSE INFORMATION:
        - Fuse Type: {fuse_type}
        - LIRA Attribute: {lira_attribute}
        - LIRA Value: {lira_value}
        - Fuse Name: {fuse_name}
        - Actual Value from Report: {actual_value}
        - HSD Info: {hsd_info}
        - Equation: {equation}
        - Assigned Value: {assigned_value}
        - Attribute Count: {attribute_count}
        - Fusing Recipe: {fusing_recipe}
        
        TASK:
        1. Analyze the equation and understand its logic
        2. Use the LIRA Value to evaluate the equation
        3. Handle different equation formats:
           - Dictionary lookups like {{"HEDT","1'h1"}},{{"STANDARD","1'h0"}}
           - Mathematical expressions with lineItem references
           - Conditional statements (ternary operators)
           - Verilog format conversions (1'h0, 2'h3, etc.)
           - Wherever there is a variable "fusing_recipe", assume it is always 1
        
        REQUIREMENTS:
        - If the equation is a dictionary lookup, find the key that matches the LIRA Value and return the corresponding value
        - If it's a mathematical expression, substitute the LIRA Value and calculate the result
        - Convert Verilog format (like 1'h0) to decimal numbers (0, 1, 2, 3, etc.)
        - ALWAYS return the final result as a hexadecimal value (e.g., 0x0, 0x1, 0xFF)
        - For your example: if LIRA Value is "STANDARD" and equation is {{"HEDT","1'h1"}},{{"ADVANCED","1'h0"}},{{"STANDARD","1'h0"}},{{"1SWS","1'h0"}}, the result should be 0x0 (from 1'h0)
        
        RESPONSE FORMAT:
        Please respond with ONLY the hexadecimal result value (e.g., 0x0, 0x1, 0xFF). 
        Do NOT provide JSON format or explanations.
        Just return the hexadecimal value directly.
        
        Evaluate this equation now:
        """
        
        try:
            # Prepare messages for OpenAI
            messages = [
                {
                    "role": "system",
                    "content": "You are an expert fuse configuration evaluator specializing in evaluating complex fuse equations with LIRA attributes. Always provide precise calculations and clear explanations."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ]
            
            # Get response from OpenAI
            print(f"   🤖 Sending equation to OpenAI for evaluation...")
            response = self.openai_connector.run_prompt(messages)
            
            if response and 'response' in response:
                ai_response = response['response'].strip()
                
                # Process the direct hexadecimal response
                try:
                    # Clean up the response - remove any extra text
                    lines = ai_response.split('\n')
                    hex_result = None
                    
                    # Look for hexadecimal value in the response
                    for line in lines:
                        line = line.strip()
                        # Match hexadecimal patterns like 0x0, 0x1, 0xFF, etc.
                        if line.startswith('0x') or line.startswith('0X'):
                            hex_result = line
                            break
                        # Also check for simple hex without 0x prefix
                        elif line and all(c in '0123456789ABCDEFabcdef' for c in line):
                            hex_result = f"0x{line.upper()}"
                            break
                    
                    if hex_result:
                        # Validate it's a proper hex value
                        try:
                            int(hex_result, 16)  # This will throw if invalid hex
                            explanation = f"OpenAI evaluated equation and returned: {hex_result}"
                            return hex_result, explanation, 'Success', summary
                        except ValueError:
                            pass
                    
                    # If no valid hex found, try to extract number and convert to hex
                    import re
                    numbers = re.findall(r'\b\d+\b', ai_response)
                    if numbers:
                        try:
                            decimal_value = int(numbers[0])
                            hex_result = f"0x{decimal_value:X}"
                            explanation = f"OpenAI returned {decimal_value}, converted to hex: {hex_result}"
                            return hex_result, explanation, 'Success', summary
                        except ValueError:
                            pass
                    
                    # Fallback: return the raw response but mark as needing conversion
                    explanation = f"OpenAI response: {ai_response}"
                    return "0x0", explanation, 'Warning', summary

                except Exception as e:
                    error_msg = f"Error processing OpenAI response: {str(e)}"
                    return "0x0", error_msg, 'Error'
            else:
                return "0x0", "OpenAI did not provide a response", "Error"
                
        except Exception as e:
            error_msg = f"Error calling OpenAI: {str(e)}"
            print(f"   ❌ {error_msg}")
            return "OpenAI Error", error_msg, "Error"
    
    def compare_values(self, calculated_result: str, actual_value: str) -> str:
        """
        Compare the calculated result with the actual value from report
        Handles various formats including Verilog format like 16'h0050
        
        Args:
            calculated_result (str): The OpenAI calculated result (in hex format)
            actual_value (str): The actual value from the report
            
        Returns:
            str: "True" if values match, "False" if they don't match
        """
        if not calculated_result or not actual_value:
            return "False"
        
        # Clean up both values
        calc_clean = str(calculated_result).strip()
        actual_clean = str(actual_value).strip()
        
        # Debug print for troubleshooting
        print(f"   🔍 Comparing: '{calc_clean}' vs '{actual_clean}'")
        
        # Direct string comparison first (case-insensitive)
        if calc_clean.upper() == actual_clean.upper():
            print(f"   ✅ Direct string match")
            return "True"
        
        # Try to normalize both values for comparison
        try:
            # Handle hex format comparison with Verilog support
            calc_normalized = self.normalize_hex_value(calc_clean)
            actual_normalized = self.normalize_hex_value(actual_clean)
            
            print(f"   🔍 Normalized: '{calc_normalized}' vs '{actual_normalized}'")
            
            if calc_normalized == actual_normalized:
                print(f"   ✅ Normalized hex match")
                return "True"
            
            # Try decimal comparison as fallback
            calc_decimal = self.convert_to_decimal(calc_clean)
            actual_decimal = self.convert_to_decimal(actual_clean)
            
            print(f"   🔍 Decimal values: {calc_decimal} vs {actual_decimal}")
            
            if calc_decimal is not None and actual_decimal is not None:
                result = "True" if calc_decimal == actual_decimal else "False"
                if result == "True":
                    print(f"   ✅ Decimal value match")
                else:
                    print(f"   ❌ Values don't match")
                return result
                
        except Exception as e:
            print(f"   ⚠️ Error comparing values: {e}")
        
        print(f"   ❌ No match found")
        return "False"
    
    def normalize_hex_value(self, value: str) -> str:
        """
        Normalize a hex value to a standard format for comparison
        Handles various formats including Verilog format like 16'h0050, 1'h1
        
        Args:
            value (str): The value to normalize
            
        Returns:
            str: Normalized hex value (e.g., "0x50")
        """
        if not value:
            return "0x0"
        
        value = str(value).strip().upper()
        
        # Handle Verilog format: width'base+value (e.g., 16'h0050, 1'h1)
        # Comprehensive pattern to handle various apostrophe-like characters
        verilog_pattern = r"(\d+)[\'\'\`´ʼ]([hbdo])([0-9a-fA-F]+)"
        match = re.search(verilog_pattern, value, re.IGNORECASE)
        
        if match:
            width = int(match.group(1))
            base = match.group(2).lower()
            hex_value = match.group(3)
            
            if base == 'h':  # Hexadecimal
                # Remove leading zeros and format properly
                decimal_val = int(hex_value, 16)
                return f"0x{decimal_val:X}"
            elif base == 'b':  # Binary
                decimal_val = int(hex_value, 2)
                return f"0x{decimal_val:X}"
            elif base == 'd':  # Decimal
                decimal_val = int(hex_value, 10)
                return f"0x{decimal_val:X}"
            elif base == 'o':  # Octal
                decimal_val = int(hex_value, 8)
                return f"0x{decimal_val:X}"
        
        # If already in 0x format, validate and return
        if value.startswith('0X'):
            try:
                decimal_val = int(value, 16)  # Validate it's proper hex
                return f"0x{decimal_val:X}"  # Normalize format
            except ValueError:
                pass
        
        # If it's just hex digits, add 0x prefix
        if value and all(c in '0123456789ABCDEF' for c in value):
            decimal_val = int(value, 16)
            return f"0x{decimal_val:X}"
        
        # Try to convert decimal to hex
        try:
            decimal_val = int(value)
            return f"0x{decimal_val:X}"
        except ValueError:
            pass
        
        return "0x0"
    
    def convert_to_decimal(self, value: str) -> int:
        """
        Convert various formats to decimal for comparison
        Handles Verilog format like 16'h0050, 1'h1
        
        Args:
            value (str): The value to convert
            
        Returns:
            int: Decimal value, or None if conversion fails
        """
        if not value:
            return 0
        
        value = str(value).strip().upper()
        
        try:
            # Handle Verilog format: width'base+value (e.g., 16'h0050, 1'h1)
            # Comprehensive pattern to handle various apostrophe-like characters
            verilog_pattern = r"(\d+)[\'\'\`´ʼ]([hbdo])([0-9a-fA-F]+)"
            match = re.search(verilog_pattern, value, re.IGNORECASE)
            
            if match:
                width = int(match.group(1))
                base = match.group(2).lower()
                hex_value = match.group(3)
                
                if base == 'h':  # Hexadecimal
                    return int(hex_value, 16)
                elif base == 'b':  # Binary
                    return int(hex_value, 2)
                elif base == 'd':  # Decimal
                    return int(hex_value, 10)
                elif base == 'o':  # Octal
                    return int(hex_value, 8)
            
            # Try hex format with 0x prefix
            if value.startswith('0X'):
                return int(value, 16)
            
            # Try pure hex digits
            if value and all(c in '0123456789ABCDEF' for c in value):
                return int(value, 16)
            
            # Try decimal
            return int(value)
            
        except ValueError:
            return None
    
    def extract_hsd_summary_from_response(self, response_text: str, hsd_id: str) -> str:
        """
        Extract the summary section from HSD analysis response.
        
        Args:
            response_text (str): The full response from OpenAI HSD analysis
            hsd_id (str): The HSD ID for fallback identification
            
        Returns:
            str: Extracted summary text or fallback message
        """
        if not response_text or not response_text.strip():
            return f"No summary available for HSD {hsd_id}"
        
        response_lines = response_text.strip().split('\n')
        
        # Look for the Summary section in the response
        summary_lines = []
        in_summary_section = False
        
        for line in response_lines:
            line = line.strip()
            
            # Start capturing when we find the Summary section
            if line.startswith('**Summary:**'):
                in_summary_section = True
                # Extract content after the "**Summary:**" marker
                summary_content = line.replace('**Summary:**', '').strip()
                if summary_content:
                    summary_lines.append(summary_content)
                continue
            
            # If we're in summary section and hit another section marker, stop
            if in_summary_section and line.startswith('**') and ':' in line:
                break
                
            # If we're in summary section, collect the line
            if in_summary_section and line:
                summary_lines.append(line)
        
        # Join the summary lines
        if summary_lines:
            extracted_summary = ' '.join(summary_lines).strip()
            # Clean up any extra formatting
            extracted_summary = extracted_summary.replace('**', '').strip()
            return extracted_summary
        
        # Fallback: Try to get first meaningful paragraph
        meaningful_lines = []
        for line in response_lines:
            line = line.strip()
            if line and not line.startswith('**') and not line.startswith('#'):
                meaningful_lines.append(line)
                # Limit to first 2-3 sentences for summary
                if len(meaningful_lines) >= 3:
                    break
        
        if meaningful_lines:
            fallback_summary = ' '.join(meaningful_lines).strip()
            return fallback_summary[:200] + "..." if len(fallback_summary) > 200 else fallback_summary
        
        # Final fallback
        return f"Summary extraction failed for HSD {hsd_id} - see full analysis file"
    
    def process_excel_data(self, column_mapping: Dict[str, str] = None) -> List[Dict]:
        """
        Process all rows in the Excel data and evaluate equations using OpenAI
        
        Args:
            column_mapping (Dict[str, str]): Optional custom column mapping (not used in current implementation)
        
        Returns:
            List[Dict]: Results for each row
        """
        if self.data is None:
            print("❌ No data loaded. Please load Excel file first.")
            return []
        
        if not self.openai_connector:
            print("❌ OpenAI connector not available. Cannot evaluate equations.")
            return []
        
        results = []
        total_rows = len(self.data)
        
        print(f"\n🔄 Processing {total_rows} rows with OpenAI evaluation...")
        print(f"📋 Using columns: {list(self.column_names.values())}")
        if column_mapping:
            print(f"🔧 Custom column mapping provided: {column_mapping}")
        
        for index, row in self.data.iterrows():
            try:
                print(f"\n📝 Processing Row {index + 1}/{total_rows}")
                
                # Extract all row data
                row_data = {}
                for col_key, col_name in self.column_names.items():
                    row_data[col_name] = row.get(col_name, '')
                
                # Print row information using new column names
                print(f"   🔹 Fuse: {row_data.get('Fuse_Name', 'Unknown')}")
                print(f"   🔹 LIRA Attribute: {row_data.get('LIRA Attributes', 'Unknown')}")
                print(f"   🔹 LIRA Value: {row_data.get('LIRA Value', 'Unknown')}")
                print(f"   🔹 Equation: {str(row_data.get('Fuse_Equation', 'Unknown'))[:100]}...")
                
                # Evaluate using OpenAI
                result, explanation, status, summary = self.evaluate_equation_with_openai(row_data)
                
                # Compare with actual value from report using new column name
                actual_value = row_data.get('Actual_Value_from_Report', '')
                comparison_result = self.compare_values(result, actual_value)
                
                # Store the result using new column structure
                row_result = {
                    'Row': index + 1,
                    'Line_Number': row_data.get('Line_Number', ''),
                    'Fuse_Type': row_data.get('Fuse_Type', ''),
                    'Fuse_Name': row_data.get('Fuse_Name', ''),
                    'LIRA_Attributes': row_data.get('LIRA Attributes', ''),
                    'LIRA_Value': row_data.get('LIRA Value', ''),
                    'Attribute_Count': row_data.get('Attribute_Count', ''),
                    'Assigned_Value': row_data.get('Assigned_Value', ''),
                    'Actual_Value_from_Report': actual_value,
                    'HSD_Info': row_data.get('HSD_Info', ''),
                    'Original_Equation': row_data.get('Fuse_Equation', ''),
                    'OpenAI_Calculated_Result': result,
                    'Values_Match': comparison_result,
                    'OpenAI_Explanation': explanation,
                    'Evaluation_Status': status,
                    'Fccb_hsd_Summary': summary
                }
                
                results.append(row_result)
                
                print(f"   ✅ Result: {result}")
                if status == 'Error':
                    print(f"   ❌ Error: {explanation}")
                
                # Add a small delay to avoid rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                error_result = {
                    'Row': index + 1,
                    'Line_Number': row.get('Line_Number', ''),
                    'Fuse_Type': row.get('Fuse_Type', ''),
                    'Fuse_Name': row.get('Fuse_Name', ''),
                    'LIRA_Attributes': row.get('LIRA Attributes', ''),
                    'LIRA_Value': row.get('LIRA Value', ''),
                    'Attribute_Count': row.get('Attribute_Count', ''),
                    'Assigned_Value': row.get('Assigned_Value', ''),
                    'Actual_Value_from_Report': row.get('Actual_Value_from_Report', ''),
                    'HSD_Info': row.get('HSD_Info', ''),
                    'Original_Equation': str(row.get('Fuse_Equation', '')),
                    'OpenAI_Calculated_Result': f'ERROR: {str(e)}',
                    'Values_Match': 'False',
                    'OpenAI_Explanation': f'Processing Error: {str(e)}',
                    'Evaluation_Status': 'Error',
                    'Fccb_hsd_Summary': 'NA'
                }
                results.append(error_result)
                print(f"   ❌ Row {index + 1} processing error: {e}")
        
        self.results = results
        print(f"\n✅ Processed {len(results)} rows with OpenAI evaluation")
        return results
    
    def save_results_to_excel(self, output_path: str = None) -> bool:
        """
        Save processing results to Excel file with timestamp and highlighting
        
        Args:
            output_path (str): Path for output Excel file (optional)
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.results:
            print("❌ No results to save. Please process data first.")
            return False
        
        # Generate timestamped filename if no output path provided
        if not output_path:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"Q7YT_fuse_extraction_results_with_fuse_report_evaluated_results_{timestamp}.xlsx"
            output_path = get_fuse_report_file_path(filename)
        else:
            # If output_path is provided, ensure it's in the fuse_report directory
            fuse_report_dir = ensure_fuse_report_directory()
            if not str(output_path).startswith(str(fuse_report_dir)):
                output_path = get_fuse_report_file_path(Path(output_path).name)
        
        try:
            # Convert results to DataFrame
            df_results = pd.DataFrame(self.results)
            print(f"📊 Preparing to save {len(df_results)} rows to Excel with highlighting...")
            
            # Count matches for reporting
            true_matches = len([r for r in self.results if str(r.get('Values_Match', '')).upper() == 'TRUE'])
            false_matches = len([r for r in self.results if str(r.get('Values_Match', '')).upper() == 'FALSE'])
            print(f"🎯 Highlighting: {false_matches} false matches (red), {true_matches} true matches (green)")
            
            # Create Excel writer with xlsxwriter engine for formatting
            with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
                # Write main results (this creates the basic data)
                df_results.to_excel(writer, sheet_name='Results', index=False)
                
                # Create summary sheet
                summary_data = self.generate_summary()
                if summary_data:
                    df_summary = pd.DataFrame([summary_data])
                    df_summary.to_excel(writer, sheet_name='Summary', index=False)
                
                # Get workbook and worksheet objects for formatting
                workbook = writer.book
                worksheet = writer.sheets['Results']
                
                # Define formats
                header_format = workbook.add_format({
                    'bold': True,
                    'text_wrap': True,
                    'valign': 'top',
                    'bg_color': '#D7E4BC',
                    'border': 1,
                    'font_size': 11
                })
                
                # Format for highlighting false matches (more prominent red)
                false_match_format = workbook.add_format({
                    'bg_color': '#FFD0D0',  # Slightly darker red
                    'border': 1,
                    'font_size': 10
                })
                
                # Format for true matches (light green)
                true_match_format = workbook.add_format({
                    'bg_color': '#D0FFD0',  # Slightly darker green
                    'border': 1,
                    'font_size': 10
                })
                
                # Default format for rows without match data
                default_format = workbook.add_format({
                    'border': 1,
                    'font_size': 10
                })
                
                # Re-write headers with formatting
                for col_num, value in enumerate(df_results.columns.values):
                    worksheet.write(0, col_num, value, header_format)
                
                # Apply row-by-row formatting based on Values_Match column
                if 'Values_Match' in df_results.columns:
                    print(f"🎨 Applying conditional formatting to rows...")
                    
                    # Process each data row
                    highlighted_false = 0
                    highlighted_true = 0
                    
                    for row_idx, (_, row_data) in enumerate(df_results.iterrows()):
                        excel_row = row_idx + 1  # Excel row (1-based, accounting for header)
                        match_value = str(row_data.get('Values_Match', '')).upper()
                        
                        # Determine format based on match value
                        if match_value == 'FALSE':
                            row_format = false_match_format
                            highlighted_false += 1
                        elif match_value == 'TRUE':
                            row_format = true_match_format
                            highlighted_true += 1
                        else:
                            row_format = default_format
                        
                        # Apply format to entire row
                        for col_idx, col_name in enumerate(df_results.columns):
                            cell_value = row_data[col_name]
                            # Handle different data types properly
                            if pd.isna(cell_value):
                                cell_value = ""
                            elif isinstance(cell_value, (int, float)):
                                cell_value = cell_value
                            else:
                                cell_value = str(cell_value)
                            
                            worksheet.write(excel_row, col_idx, cell_value, row_format)
                    
                    print(f"✅ Applied highlighting: {highlighted_false} red rows, {highlighted_true} green rows")
                else:
                    print("⚠️ 'Values_Match' column not found, no highlighting applied")
                
                # Adjust column widths for better readability with new column structure
                column_widths = {
                    'Row': 8,
                    'Line_Number': 12,
                    'Fuse_Type': 15,
                    'Fuse_Name': 25,
                    'LIRA_Attributes': 25,
                    'LIRA_Value': 20,
                    'Attribute_Count': 15,
                    'Assigned_Value': 20,
                    'Actual_Value_from_Report': 30,
                    'HSD_Info': 20,
                    'Original_Equation': 50,
                    'OpenAI_Calculated_Result': 30,
                    'Values_Match': 15,
                    'OpenAI_Explanation': 60,
                    'Evaluation_Status': 18,
                    'Fccb_hsd_Summary': 80
                }
                
                for col_name, width in column_widths.items():
                    if col_name in df_results.columns:
                        col_idx = df_results.columns.get_loc(col_name)
                        worksheet.set_column(col_idx, col_idx, width)
                
                # Freeze the header row for easier viewing
                worksheet.freeze_panes(1, 0)
            
            print(f"✅ Results saved to: {output_path}")
            print(f"🎨 Excel file includes row highlighting: False matches (red), True matches (green)")
            return True
            
        except Exception as e:
            print(f"❌ Error saving results: {e}")
            import traceback
            print(f"🔍 Detailed error: {traceback.format_exc()}")
            return False
    
    def generate_summary(self) -> Dict:
        """
        Generate summary statistics from results
        
        Returns:
            Dict: Summary statistics
        """
        if not self.results:
            return {}
        
        total_rows = len(self.results)
        successful = len([r for r in self.results if r['Evaluation_Status'] == 'Success'])
        errors = len([r for r in self.results if r['Evaluation_Status'] == 'Error'])
        warnings = len([r for r in self.results if r['Evaluation_Status'] == 'Warning'])
        
        # Count value matches
        true_matches = len([r for r in self.results if str(r.get('Values_Match', '')).upper() == 'TRUE'])
        false_matches = len([r for r in self.results if str(r.get('Values_Match', '')).upper() == 'FALSE'])
        
        # Count unique fuses
        unique_fuses = len(set([r['Fuse_Name'] for r in self.results if r['Fuse_Name']]))
        
        # Count unique attributes using new column name
        unique_attributes = len(set([r['LIRA_Attributes'] for r in self.results if r['LIRA_Attributes']]))
        
        summary = {
            'Total_Rows_Processed': total_rows,
            'Successful_Evaluations': successful,
            'Errors': errors,
            'Warnings': warnings,
            'Success_Rate': f"{(successful/total_rows*100):.1f}%" if total_rows > 0 else "0%",
            'Value_Matches_True': true_matches,
            'Value_Matches_False': false_matches,
            'Match_Rate': f"{(true_matches/total_rows*100):.1f}%" if total_rows > 0 else "0%",
            'Unique_Fuses': unique_fuses,
            'Unique_LIRA_Attributes': unique_attributes,
            'Processing_Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return summary
    
    def export_results(self, output_file: str = None) -> str:
        """
        Export results to Excel file with timestamp and highlighting
        
        Args:
            output_file (str): Output file path (optional)
            
        Returns:
            str: Path to the exported file
        """
        if not self.results:
            print("❌ No results to export. Please process data first.")
            return ""
        
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"Q7YT_fuse_extraction_results_with_fuse_report_evaluated_results_{timestamp}.xlsx"
            output_file = get_fuse_report_file_path(filename)
        else:
            # If output_file is provided, ensure it's in the fuse_report directory
            fuse_report_dir = ensure_fuse_report_directory()
            if not str(output_file).startswith(str(fuse_report_dir)):
                output_file = get_fuse_report_file_path(Path(output_file).name)
        
        # Use the enhanced save_results_to_excel method which includes highlighting
        success = self.save_results_to_excel(output_file)
        
        if success:
            print(f"📊 Results exported to: {output_file}")
            return output_file
        else:
            print(f"❌ Error exporting results")
            return ""
    
    def print_summary(self):
        """Print a summary of the evaluation results"""
        if not self.results:
            print("❌ No results to summarize.")
            return
        
        total_rows = len(self.results)
        successful_rows = len([r for r in self.results if r['Evaluation_Status'] == 'Success'])
        error_rows = total_rows - successful_rows
        
        # Count value matches
        true_matches = len([r for r in self.results if str(r.get('Values_Match', '')).upper() == 'TRUE'])
        false_matches = len([r for r in self.results if str(r.get('Values_Match', '')).upper() == 'FALSE'])
        
        print(f"\n📋 EVALUATION SUMMARY:")
        print(f"   📊 Total rows processed: {total_rows}")
        print(f"   ✅ Successful evaluations: {successful_rows}")
        print(f"   ❌ Failed evaluations: {error_rows}")
        print(f"   📈 Success rate: {successful_rows/total_rows*100:.1f}%")
        print(f"   🎯 Value matches (True): {true_matches}")
        print(f"   ⚠️  Value mismatches (False): {false_matches}")
        print(f"   📊 Match rate: {true_matches/total_rows*100:.1f}%")
        
        # Show first few results as examples
        print(f"\n📄 SAMPLE RESULTS:")
        for i, result in enumerate(self.results[:5]):
            match_symbol = "✅" if str(result.get('Values_Match', '')).upper() == 'TRUE' else "❌"
            print(f"   Row {result['Row']}: {result['Fuse_Name']} -> {result['OpenAI_Calculated_Result']} {match_symbol}")
        
        if len(self.results) > 5:
            print(f"   ... and {len(self.results) - 5} more rows")
        
        # Show false matches if any
        false_match_rows = [r for r in self.results if str(r.get('Values_Match', '')).upper() == 'FALSE']
        if false_match_rows:
            print(f"\n⚠️  FALSE MATCHES (Highlighted in red in Excel):")
            for i, result in enumerate(false_match_rows[:3]):  # Show first 3 false matches
                print(f"   Row {result['Row']}: Expected {result.get('Actual_Value_from_Report', 'N/A')} but got {result['OpenAI_Calculated_Result']}")
                if i >= 2:  # Limit to 3 examples
                    break
            if len(false_match_rows) > 3:
                print(f"   ... and {len(false_match_rows) - 3} more false matches")


def main():
    """Main function to run the POC"""
    parser = argparse.ArgumentParser(description="Excel Fuse Equation Evaluator POC")
    parser.add_argument("excel_file", help="Path to the Excel file")
    parser.add_argument("--sheet", help="Sheet name (optional)", default=None)
    parser.add_argument("--output", help="Output file path (optional)", default=None)
    parser.add_argument("--columns", help="Custom column mapping as JSON string (optional)", default=None)
    
    args = parser.parse_args()
    
    # Validate input file
    if not os.path.exists(args.excel_file):
        print(f"❌ Excel file not found: {args.excel_file}")
        return
    
    print(f"🚀 Starting Excel Fuse Equation Evaluator POC")
    print(f"📁 Input file: {args.excel_file}")
    
    # Initialize evaluator
    evaluator = FuseEquationEvaluator(args.excel_file)
    
    # Load Excel file
    if not evaluator.load_excel_file(args.sheet):
        return
    
    # Process column mapping if provided
    column_mapping = None
    if args.columns:
        try:
            import json
            column_mapping = json.loads(args.columns)
        except Exception as e:
            print(f"⚠️ Invalid column mapping JSON: {e}")
    
    # Process the data
    results = evaluator.process_excel_data(column_mapping)
    
    if results:
        # Print summary
        evaluator.print_summary()
        
        # Export results
        output_file = evaluator.export_results(args.output)
        
        print(f"\n✅ POC completed successfully!")
        if output_file:
            print(f"📊 Results saved to: {output_file}")


if __name__ == "__main__":
    # Example usage if run directly without arguments
    if len(sys.argv) == 1:
        print("📋 USAGE EXAMPLES:")
        print()
        print("🔹 Basic usage:")
        print("   python fuse_equation_evaluator_poc.py your_file.xlsx")
        print()
        print("🔹 With specific sheet:")
        print("   python fuse_equation_evaluator_poc.py your_file.xlsx --sheet 'Sheet1'")
        print()
        print("🔹 With custom output file:")
        print("   python fuse_equation_evaluator_poc.py your_file.xlsx --output results.xlsx")
        print()
        print("🔹 With custom column mapping:")
        print('   python fuse_equation_evaluator_poc.py your_file.xlsx --columns \'{"equation":"Fuse_Equation","lira_attribute":"LIRA_Attr","lira_value":"LIRA_Val"}\'')
        print()
        print("📋 EXPECTED EXCEL COLUMNS:")
        print("   • Equation/Formula column (contains fuse equations)")
        print("   • LIRA Attribute column (contains LIRA attribute names)")
        print("   • LIRA Value column (contains LIRA attribute values)")
        print("   • Fuse Name column (optional, for identification)")
        print()
        print("📊 SUPPORTED EQUATION FORMATS:")
        print('   • Dictionary lookup: {"HEDT","1\'h1"},{"STANDARD","1\'h0"}')
        print("   • Mathematical: lineItem.attr.Value * 2 + 5")
        print("   • Conditional: condition ? true_value : false_value")
        print("   • Verilog format: 1'h0, 2'h3, etc.")
    else:
        main()
