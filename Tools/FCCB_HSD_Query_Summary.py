#############################################################################################
# Version : 1.0
# Author  : Ravoor, Abhishek (abhishek.ravoor@intel.com) and Bhogade, Vishal B (vishal.b.bhogade@intel.com)
# Date	  : 21-Jan-2025
# Change  : Creation
#
# ---------------------------------------------------------------------------------------
# Description:
# This script takes a queryID as an input from the user and dumps all the fields of each HSD
# into a json file and also it takes a prompt/user_action_prompt from the user and passess it to OpenAI
# API and the prompt is applied on the stored json file and output is written to the
# openai_response.txt file
# -------------------------------------------------------------------------------------------
# The description will be updated by the author as and when the flow gets updated.
# -------------------------------------------------------------------------------------------
# NOTE: PLEASE ENSURE TO MAINTAIN REVISION HISTORY BELOW WHEN UPDATING CODE
# -------------------------------------------------------------------------------------------
#############################################################################################


from openai import AzureOpenAI
import requests
import httpx
import openai
import urllib3
import http.client
import traceback
import os
import time
import json
import ast
from datetime import datetime
from pathlib import Path
from requests_kerberos import HTTPKerberosAuth
import argparse
import pandas as pd
import re
import sys
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Create logs directory function
def ensure_logs_directory():
    """Create the FCCB_HSD_Query_Summary_Logs directory if it doesn't exist"""
    logs_dir = Path("Tools/FCCB_HSD_Query_Summary_Logs")
    logs_dir.mkdir(exist_ok=True)
    return logs_dir

def get_log_file_path(filename):
    """Get the full path for a file in the FCCB_HSD_Query_Summary_Logs directory"""
    logs_dir = ensure_logs_directory()
    return logs_dir / filename

# Import our environment configuration module
try:
    from env_config import load_environment_config, get_openai_key, get_azure_openai_config
    ENV_CONFIG_AVAILABLE = True
except ImportError:
    ENV_CONFIG_AVAILABLE = False
    print("⚠️  env_config.py not found. Using basic environment variable loading.")

requests.packages.urllib3.disable_warnings()

# Load environment configuration
if ENV_CONFIG_AVAILABLE:
    # Use our enhanced environment loading
    load_environment_config()
    openai_key = get_openai_key()
else:
    # Fallback to basic environment variable loading
    if "OPENAI_KEY" in os.environ:
        openai_key = os.environ["OPENAI_KEY"]
    # backwards compatibility with lowercase key as older versions of this connector used it like that
    elif "openai_key" in os.environ:
        openai_key = os.environ["openai_key"]
    else:
        openai_key = None

if not openai_key:
    print("ERROR - Please set an openAI key with environment variable 'OPENAI_KEY'")
    print('''\nINFO - In order to get your openAI key follow these steps:
    1. Register for iVE GenAI Hackathon at https://forms.microsoft.com/Pages/ResponsePage.aspx?id=iI3JRkTj1E6Elk7XcS4lXclO-okE9hFNszyNpymG1CFURVNDOE1LTTRYRFRWNzE5VjI1RkJWQTk1US4u
    2. Go to https://valgpt-api.laas.intel.com/
    3. Select product 'genAi-hackaton'
    4. Click on button "Create New"
    5. Enter a key name to use. This is for your own tracking. i.e., 'iVE Hackaton Key'
    6. Copy and save the generated key. You won't be able to see it later.
    7. Export your key to environment variable 'OPENAI_KEY'cd ..
          
  ''')
    raise Exception("openAI key not set for %s. More info above."%(os.path.basename(__file__),))

DEFAULT_DEPLOYMENT_NAME = "gpt-4o"

# create an instance of the AzureOpenAI class
# Why pass both 'api_key' and default_headers={"Ocp-Apim-Subscription-Key"}?
#    Not sure. Passing only api_key seems to work
#    Passing only default_headers... (with a valid key) and api_key with any string also seems to work
#    We decided to keep both
client = AzureOpenAI(
    api_version = "2024-12-01-preview", #Todo- Update to the latest
    api_key = openai_key, #TODO - Need to update the API KEY and it shouldn't be hard coded it
    base_url = "https://laasapim01.laas.icloud.intel.com/azopenai",
    default_headers={"Ocp-Apim-Subscription-Key" :openai_key},
    http_client=httpx.Client(verify=False)
    )


class HsdConnector:
   
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
        fields = ["id","title", "description", "status", "comments","sighting.forum_notes"]

        if fields == "":  # Backwards compatibility
            fields = None
        assert fields is None or (len(fields) > 0 and type(fields) != str and all([type(f) == str for f in fields])), \
            "fields must be None or a list\\iterator of strings. Got %s." % (repr(fields),)
        retry = 10
        while (retry > 0):
            try:
                req = "https://hsdes-api.intel.com/rest/article/" + str(hsd_id)
                #req = "https://hsdes.intel.com/appstore/article-one/#/article/" + str(hsd_id)
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
                   # Get full path in hsd_summary_logs directory
                   full_file_path = get_log_file_path(hsd_id_data_file)
                   with open(full_file_path, 'w', encoding='utf-8') as final_file:
                       json.dump(response_data, final_file, indent=4, ensure_ascii=False)
                       print(f"Full JSON data has been saved to '{full_file_path}'\n")
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
   
    def get_multiple_hsd_data_in_file(self, hsd_ids, fields=None):
        """
        Fetches detailed information for multiple HSD IDs and saves all data to a single JSON file.
        The method sends GET requests to the HSD API for each HSD ID and accumulates all data.
        
        Note: The HSD API requires Kerberos authentication. Meaning it can only be executed locally and not over cloud.
        Parameters:
        hsd_ids (list): List of HSD IDs to fetch information for.
        fields (List<str>): fields to include in the response, list of strings (optional). If not defined, returns all fields.
        Returns:
        str: File name of the JSON data file containing accumulated data from all HSD IDs
        
        Raises:
        requests.exceptions.HTTPError: If the HTTP request encounters an error or if the response status code is not 200 OK.
        urllib3.exceptions.MaxRetryError: If the HSD could not be found and reached MAX retries count (10)
        requests.exceptions.ProxyError: Problem with proxy settings
        http.client.RemoteDisconnected: During the query the remote was disconnected
        """
        # Only collect the specified fields
        #fields = ["id","title", "description", "subject", "owner", "status", "comments", "tenant", "failing_info", "component","env_found"]
        fields = ["id","title", "description", "status", "comments","forum_notes"]
        if fields == "":  # Backwards compatibility
            fields = None
        assert fields is None or (len(fields) > 0 and type(fields) != str and all([type(f) == str for f in fields])), \
            "fields must be None or a list\\iterator of strings. Got %s." % (repr(fields),)
        
        if not hsd_ids or not isinstance(hsd_ids, list):
            raise ValueError("hsd_ids must be a non-empty list")
        
        # Generate timestamp and dynamic filename
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        hsd_data_file = f"hsd_multiple_{len(hsd_ids)}hsds_{timestamp}.json"
        # Get full path in hsd_summary_logs directory
        full_file_path = get_log_file_path(hsd_data_file)
        
        # Initialize accumulated data structure
        accumulated_data = {"data": []}
        successful_count = 0
        failed_count = 0
        
        print(f"Processing {len(hsd_ids)} HSD IDs...")
        
        for i, hsd_id in enumerate(hsd_ids, 1):
            print(f"Processing HSD {i}/{len(hsd_ids)}: {hsd_id}")
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
                        # Handle both single data item and list of data items
                        if isinstance(response_data["data"], list):
                            accumulated_data["data"].extend(response_data["data"])
                        else:
                            accumulated_data["data"].append(response_data["data"])
                        successful_count += 1
                        success = True
                    else:
                        print(f"  ✗ No data found for HSD ID: {hsd_id}")
                        failed_count += 1
                        success = True  # Don't retry for no data
                        
                except urllib3.exceptions.MaxRetryError:
                    print(f'  ⚠ Got "urllib3.exceptions.MaxRetryError" for HSD {hsd_id}, retrying {retry - 1} more attempts')
                    retry -= 1
                except requests.exceptions.ProxyError:
                    print(f'  ⚠ Got "requests.exceptions.ProxyError" for HSD {hsd_id}, retrying {retry - 1} more attempts')
                    retry -= 1
                except http.client.RemoteDisconnected:
                    print(f'  ⚠ Got "http.client.RemoteDisconnected" for HSD {hsd_id}, retrying {retry - 1} more attempts')
                    retry -= 1
                except Exception as e:
                    print(f'  ✗ Got unknown exception for HSD {hsd_id}: {traceback.format_exc()}, retrying {retry - 1} more attempts')
                    retry -= 1
            
            if not success:
                print(f"  ✗ Failed to fetch data for HSD ID: {hsd_id} after all retries")
                failed_count += 1
        
        # Save the accumulated data to file
        with open(full_file_path, 'w', encoding='utf-8') as final_file:
            json.dump(accumulated_data, final_file, indent=4, ensure_ascii=False)
        
        print(f"\n📊 Processing Summary:")
        print(f"  • Total HSDs processed: {len(hsd_ids)}")
        print(f"  • Successful: {successful_count}")
        print(f"  • Failed: {failed_count}")
        print(f"  • HSDs with content data: {len(accumulated_data['data'])}")
        print(f"  • Data saved to: '{full_file_path}'")
        
        return str(full_file_path)
    
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
        fields = ["id","title", "description", "status", "comments","forum_notes"]
        
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
            # Get full path in hsd_summary_logs directory
            full_batch_path = get_log_file_path(batch_file)
            
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

    def fetch_hsd_ids_from_query(self, query_id):
        """
        Fetch all HSD IDs from a given query ID using the HSD API
        
        Parameters:
        query_id (str): The query ID to fetch HSD IDs from
        
        Returns:
        dict: A dictionary containing:
            - hsd_ids: List of HSD IDs found in the query
            - total_count: Total number of HSDs in the query
            - query_id: The original query ID
            - error: Error message if any
        """
        try:
            # Construct the URL dynamically
            base_url = "https://hsdes-api.intel.com/rest/query/execution/"
            req = f"{base_url}{query_id}"
            headers = {'Content-type': 'application/json'}
            
            # Get initial response to determine total count
            response_data = self._get_response(req, headers)
            
            # Extract the total number of HSDs
            total_hsds = response_data.get("total", 0)
            if total_hsds > 0:
                print(f"Total HSD entries found: {total_hsds}")

                # Construct the updated URL with max_results parameter to get all entries
                # Option 1: Use max_results to get all HSDs (default returns all fields)
                # full_query_url = f"{req}?max_results={total_hsds}"

                # Option 2: Use fields parameter to get only the 'id' field for each HSD
                # This is more efficient if you only want HSD IDs and no other data.
                full_query_url = f"{req}?max_results={total_hsds}&fields=id"

                # Option 3: Use fields to get a minimal set (id, title, status, etc.)
                # full_query_url = f"{req}?max_results={total_hsds}&fields=id,title,status"
                
                # Fetch full data
                full_response_data = self._get_response(full_query_url, headers)

                # Extract HSD IDs from the response
                if "data" in full_response_data and isinstance(full_response_data["data"], list):
                    hsd_ids = [item.get("id") for item in full_response_data["data"] if item.get("id")]
                    print(f"Extracted {len(hsd_ids)} HSD IDs from query {query_id}")
                    # Save full response to the final output file
                    return hsd_ids
                
        except Exception as e:
            error_msg = f"An error occurred while fetching HSD IDs from query {query_id}: {e}"
            print(error_msg)
            return {
                "error": error_msg,
                "query_id": query_id
            }

class OpenAIConnector:
    # Initialize the OpenAI connector class
    def __init__(self, deployment_name=None):
        if deployment_name is None:
            deployment_name = DEFAULT_DEPLOYMENT_NAME
        self.deployment_name = deployment_name

    # Run the prompt on the OpenAI model
    def run_prompt(self, prompt):
        '''
        See documentation at
            https://platform.openai.com/docs/guides/text-generation/chat-completions-api
            https://platform.openai.com/docs/api-reference/chat/create
        '''
        # Display tokens consumed before running the prompt
        print("Tokens consumed before run_prompt: 0")  # Initially, no tokens are consumed

        # Record the start time
        start_time = time.time()

        completion = client.chat.completions.create(
            model=self.deployment_name,
            messages=prompt
        )

        # Record the end time
        end_time = time.time()

        # Calculate the time taken for the query
        time_taken = end_time - start_time

        # Display tokens consumed after completion is received
        prompt_tokens = completion.usage.prompt_tokens
        completion_tokens = completion.usage.completion_tokens
        total_tokens = completion.usage.total_tokens

        print(f"Prompt tokens: {prompt_tokens}")
        print(f"Completion tokens: {completion_tokens}")
        print(f"Total tokens consumed: {total_tokens}")
        print(f"Time taken for query execution: {time_taken:.2f} seconds")

        gpt_response = completion.choices[0].message.content
        return {
            "response": gpt_response
        }

    def run_prompt_with_json(self, hsd_query_data_file, system_prompt, user_action_prompt):
        try:
            with open(hsd_query_data_file, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
                json_data_str = json.dumps(json_data, indent=4)
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_action_prompt + "/n" + json_data_str},
                ]
                return self.run_prompt(messages)
        except FileNotFoundError:
            print(f"Error: File not found at '{hsd_query_data_file}'. Please check the file path.")
        except json.JSONDecodeError:
            print("Error: Failed to decode JSON. Ensure the file contains valid JSON.")
        except Exception as e:
            print(f"An unexpected error has occurred: {e}")

def standardize_json_field_names(json_data):
    """
    Standardize JSON field names to ensure consistency across all AI responses.
    Converts 'id' to 'hsd_id' if needed.
    
    Parameters:
    json_data: The JSON data (dict, list, or any structure)
    
    Returns:
    The standardized JSON data
    """
    if isinstance(json_data, dict):
        standardized = {}
        for key, value in json_data.items():
            # Convert 'id' to 'hsd_id' for consistency
            if key == 'id' and 'hsd_id' not in json_data:
                standardized['hsd_id'] = value
                print(f"     🔧 Field standardization: 'id' → 'hsd_id' (value: {value})")
            else:
                standardized[key] = standardize_json_field_names(value)
        return standardized
    elif isinstance(json_data, list):
        return [standardize_json_field_names(item) for item in json_data]
    else:
        return json_data

def parse_fccb_json_to_excel(all_responses, output_excel_file):
    """
    Optimized FCCB parser for JSON responses from all batches.
    Enhanced with better error handling and validation.
    
    Parameters:
    all_responses (list): List of response dictionaries with batch_num, response content, and output_file
    output_excel_file (str): Path for the output Excel file
    
    Returns:
    str: Path to the created Excel file, or None if failed
    """
    try:
        # Ensure output file is saved to the correct directory
        output_excel_file = get_log_file_path(f"{Path(output_excel_file).stem}.xlsx")
        #output_excel_file = ensure_output_file_path(output_excel_file)
        import pandas as pd
        import json
        import re
        import os
        
        print(f"🔍 Parsing FCCB data from {len(all_responses)} batch responses")
        
        # Enhanced validation of input
        if not all_responses:
            print(f"❌ No responses provided to parse_fccb_json_to_excel")
            return None
            
        if not isinstance(all_responses, list):
            print(f"❌ all_responses must be a list, got {type(all_responses)}")
            return None
        
        all_fccb_records = []
        processing_errors = []
        
        for i, response in enumerate(all_responses):
            # Enhanced validation for each response
            if not isinstance(response, dict):
                error_msg = f"Response {i} is not a dictionary: {type(response)}"
                print(f"❌ {error_msg}")
                processing_errors.append(error_msg)
                continue
                
            batch_num = response.get('batch_num', f'unknown_{i}')
            
            # Check if this response had an error during processing
            if 'error' in response:
                error_msg = f"Batch {batch_num} had processing error: {response['error']}"
                print(f"⚠️ {error_msg}")
                processing_errors.append(error_msg)
                continue
            content = response.get('response', '')
            output_file = response.get('output_file', '')
            
            print(f"   📦 Processing Batch {batch_num}: {output_file}")
            
            # Optimized JSON extraction - try multiple methods
            json_data = None
            
            # Method 1: Direct file reading (most efficient)
            if output_file and os.path.exists(output_file):
                try:
                    with open(output_file, 'r', encoding='utf-8') as f:
                        file_content = f.read()
                    
                    # Extract JSON from markdown if present
                    json_match = re.search(r'```json\n(.*?)\n```', file_content, re.DOTALL)
                    if json_match:
                        json_content = json_match.group(1)
                        print(f"     📝 Extracted JSON from markdown in file {os.path.basename(output_file)}")
                    else:
                        json_content = file_content.strip()
                    
                    # Clean up JSON content - remove JavaScript-style comments
                    json_content = re.sub(r'//.*(?=\n)', '', json_content)  # Remove single-line comments
                    json_content = re.sub(r'/\*.*?\*/', '', json_content, flags=re.DOTALL)  # Remove multi-line comments
                    
                    json_data = json.loads(json_content)
                    # Standardize field names immediately after parsing
                    json_data = standardize_json_field_names(json_data)
                    print(f"     ✅ Successfully parsed JSON from file {os.path.basename(output_file)}")
                    
                except (FileNotFoundError, json.JSONDecodeError) as e:
                    print(f"     ⚠️ Could not read from file {output_file}: {e}")
                    # Try to show the problematic line for debugging
                    try:
                        lines = json_content.split('\n')
                        if hasattr(e, 'lineno') and e.lineno <= len(lines):
                            print(f"     🐛 Problematic line {e.lineno}: {lines[e.lineno-1]}")
                    except:
                        pass
            
            # Method 2: Parse content string if file method failed
            if json_data is None and content:
                try:
                    # Extract JSON from markdown if present
                    json_match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
                    if json_match:
                        json_content = json_match.group(1)
                        print(f"     📝 Extracted JSON from markdown code block in batch {batch_num}")
                    else:
                        json_content = content.strip()
                    
                    # Clean up JSON content - remove JavaScript-style comments
                    json_content = re.sub(r'//.*(?=\n)', '', json_content)  # Remove single-line comments
                    json_content = re.sub(r'/\*.*?\*/', '', json_content, flags=re.DOTALL)  # Remove multi-line comments
                    
                    json_data = json.loads(json_content)
                    # Standardize field names immediately after parsing
                    json_data = standardize_json_field_names(json_data)
                    print(f"     ✅ Successfully parsed JSON from content in batch {batch_num}")
                    
                except json.JSONDecodeError as e:
                    print(f"     ❌ JSON parsing error in batch {batch_num}: {e}")
                    # Try to show the problematic line for debugging
                    try:
                        lines = json_content.split('\n')
                        if hasattr(e, 'lineno') and e.lineno <= len(lines):
                            print(f"     🐛 Problematic line {e.lineno}: {lines[e.lineno-1]}")
                    except:
                        pass
                    continue
            
            if json_data is None:
                error_msg = f"No valid JSON data found for batch {batch_num}"
                print(f"     ❌ {error_msg}")
                processing_errors.append(error_msg)
                
                # Debug: Show first 200 chars of content for investigation
                if content:
                    preview = content[:200].replace('\n', '\\n')
                    print(f"     🔍 Content preview: {preview}...")
                continue
            
            # Standardize field names to ensure consistency
            json_data = standardize_json_field_names(json_data)
            
            # Enhanced structure detection with debugging
            print(f"     📊 JSON structure type: {type(json_data)}")
            if isinstance(json_data, dict):
                print(f"     🔑 JSON keys: {list(json_data.keys())}")
            elif isinstance(json_data, list):
                print(f"     📋 JSON array length: {len(json_data)}")
                if json_data and isinstance(json_data[0], dict):
                    print(f"     🔑 First item keys: {list(json_data[0].keys())}")
            
            hsd_array = None
            
            if isinstance(json_data, list):
                # Structure 2: [HSDs] - direct array (most common)
                hsd_array = json_data
                print(f"     📊 Found {len(hsd_array)} HSD records (direct array structure)")
            elif isinstance(json_data, dict):
                if 'data' in json_data and isinstance(json_data['data'], list):
                    # Structure 1: {"data": [HSDs]}
                    hsd_array = json_data['data']
                    print(f"     📊 Found {len(hsd_array)} HSD records (data wrapper structure)")
                elif any(key in json_data for key in ['hsd_id', 'id', 'title', 'fuse_analysis']):
                    # Structure 3: Single HSD dictionary - wrap in array
                    # Handle both 'hsd_id' and 'id' field names
                    hsd_array = [json_data]
                    field_found = 'hsd_id' if 'hsd_id' in json_data else 'id' if 'id' in json_data else 'other'
                    print(f"     📊 Found 1 HSD record (single dictionary structure, key: {field_found})")
            
            if not hsd_array:
                print(f"     ❌ No valid HSD structure found in batch {batch_num}")
                continue
            
            # Optimized fuse data extraction with batch counting
            batch_fccb_count = 0
            
            for hsd_item in hsd_array:
                if not isinstance(hsd_item, dict):
                    continue
                    
                # Handle both "hsd_id" and "id" field names for consistency
                hsd_id = hsd_item.get('hsd_id', hsd_item.get('id', 'Unknown'))
                title = hsd_item.get('title', '')
                
                # If we found an 'id' field but no 'hsd_id', standardize to 'hsd_id'
                if 'id' in hsd_item and 'hsd_id' not in hsd_item:
                    print(f"     🔧 Standardizing: Found 'id' field, converting to 'hsd_id' for HSD {hsd_id}")
                
                # Extract fuse analysis data
                fuse_analysis = hsd_item.get('fuse_analysis', [])
                
                # Special handling for rejected HSDs or HSDs with no fuse analysis
                if not isinstance(fuse_analysis, list) or not fuse_analysis:
                    print(f"     ⚠️ HSD {hsd_id}: No fuse analysis data found - creating NA record")
                    # Create a placeholder record for HSDs without fuse analysis (e.g., rejected HSDs)
                    record = {
                        'HSD_ID': hsd_id,
                        'Title': title[:150] + '...' if len(title) > 150 else title,
                        'Fuse_Name': 'NA',
                        'Old_Value': 'NA',
                        'New_Value': 'NA',
                        'Die_Component': 'NA',
                        'Change_Reason': 'NA - HSD may be rejected or no fuse data available',
                        'Validation_Impact': 'NA',
                        'Functionality': 'NA',
                        'Confidence_Score': '0.0',
                        'Batch_Number': batch_num,
                        'Source_File': os.path.basename(output_file) if output_file else f'batch_{batch_num}'
                    }
                    all_fccb_records.append(record)
                    batch_fccb_count += 1
                    continue
                
                # Bulk process fuse records for this HSD
                for fuse_data in fuse_analysis:
                    if not isinstance(fuse_data, dict):
                        continue
                    
                    # Optimized record creation with minimal string operations
                    record = {
                        'HSD_ID': hsd_id,
                        'Title': title[:150] + '...' if len(title) > 150 else title,  # Truncate long titles
                        'Fuse_Name': fuse_data.get('fuse_name', ''),
                        'Old_Value': str(fuse_data.get('old_value', '')),
                        'New_Value': str(fuse_data.get('new_value', '')),
                        'Die_Component': fuse_data.get('die_component', ''),
                        'Change_Reason': fuse_data.get('change_reason', ''),
                        'Validation_Impact': fuse_data.get('validation_impact', ''),
                        'Functionality': fuse_data.get('functionality', ''),
                        'Confidence_Score': fuse_data.get('confidence_score', ''),
                        'Batch_Number': batch_num,
                        'Source_File': os.path.basename(output_file) if output_file else f'batch_{batch_num}'
                    }
                    all_fccb_records.append(record)
                    batch_fccb_count += 1
            
            print(f"     ✅ Batch {batch_num}: {batch_fccb_count} FCCB records extracted")
        
        if not all_fccb_records:
            error_msg = f"❌ No FCCB records found in any batch responses"
            if processing_errors:
                error_msg += f"\n   • {len(processing_errors)} processing errors occurred:"
                for error in processing_errors[:5]:  # Show first 5 errors
                    error_msg += f"\n     - {error}"
                if len(processing_errors) > 5:
                    error_msg += f"\n     - ... and {len(processing_errors) - 5} more errors"
            
            print(error_msg)
            print(f"   💡 Tip: Check if AI responses contain valid JSON data with 'fuse_analysis' sections")
            
            # Create an error summary Excel file for debugging
            try:
                error_df = pd.DataFrame({
                    'Batch_Number': [r.get('batch_num', 'Unknown') for r in all_responses],
                    'Processing_Status': ['Error' if 'error' in r else 'Processed' for r in all_responses],
                    'Error_Details': [r.get('error', 'No specific error') if 'error' in r else 'Successfully processed' for r in all_responses],
                    'Output_File': [r.get('output_file', 'Not specified') for r in all_responses]
                })
                
                with pd.ExcelWriter(output_excel_file, engine='openpyxl') as writer:
                    error_df.to_excel(writer, sheet_name='Processing_Errors', index=False)
                    
                    # Add processing errors sheet if any
                    if processing_errors:
                        errors_df = pd.DataFrame({'Processing_Errors': processing_errors})
                        errors_df.to_excel(writer, sheet_name='Error_Details', index=False)
                
                print(f"   📄 Error summary saved to: {output_excel_file}")
                return str(output_excel_file)  # Return the error file for investigation
                
            except Exception as excel_error:
                print(f"   ❌ Could not create error summary Excel: {excel_error}")
                return None
        
        # Optimized DataFrame creation and Excel generation
        print(f"📊 Creating Excel file with {len(all_fccb_records)} total FCCB records...")
        
        fccb_df = pd.DataFrame(all_fccb_records)
        
        # Create Excel file with optimized operations
        with pd.ExcelWriter(output_excel_file, engine='openpyxl') as writer:
            
            # Main FCCB Analysis sheet - prioritized column order
            priority_columns = ['HSD_ID', 'Fuse_Name', 'Old_Value', 'New_Value', 'Die_Component']
            detail_columns = ['Change_Reason', 'Validation_Impact', 'Functionality', 'Confidence_Score']
            meta_columns = ['Title', 'Batch_Number', 'Source_File']
            
            column_order = [col for col in priority_columns + detail_columns + meta_columns if col in fccb_df.columns]
            fccb_df_ordered = fccb_df[column_order]
            
            fccb_df_ordered.to_excel(writer, sheet_name='FCCB_Analysis', index=False)
            print(f"   ✅ FCCB_Analysis sheet: {len(fccb_df_ordered)} fuse records")
            
            # Optimized HSD Summary using groupby operations
            hsd_summary = fccb_df.groupby('HSD_ID').agg({
                'Title': 'first',
                'Fuse_Name': 'count',  # Total fuses
                'Die_Component': lambda x: ', '.join(sorted(x.unique())),
                'Fuse_Name': lambda x: x.nunique(),  # Unique fuse types
                'Change_Reason': lambda x: x.mode().iloc[0] if not x.empty else ''
            }).rename(columns={
                'Fuse_Name': 'Total_Fuses'
            }).reset_index()
            
            # Fix the duplicate column issue by recreating properly
            hsd_summary_data = []
            for hsd_id in fccb_df['HSD_ID'].unique():
                hsd_data = fccb_df[fccb_df['HSD_ID'] == hsd_id]
                hsd_summary_data.append({
                    'HSD_ID': hsd_id,
                    'Title': hsd_data['Title'].iloc[0][:100] + '...' if len(hsd_data['Title'].iloc[0]) > 100 else hsd_data['Title'].iloc[0],
                    'Total_Fuses': len(hsd_data),
                    'Die_Components': ', '.join(sorted(hsd_data['Die_Component'].unique())),
                    'Unique_Fuse_Types': hsd_data['Fuse_Name'].nunique(),
                    'Primary_Change_Reason': hsd_data['Change_Reason'].mode().iloc[0] if not hsd_data['Change_Reason'].empty else ''
                })
            
            hsd_summary_df = pd.DataFrame(hsd_summary_data)
            hsd_summary_df.to_excel(writer, sheet_name='HSD_Summary', index=False)
            print(f"   ✅ HSD_Summary sheet: {len(hsd_summary_df)} HSD records")
            
            # Optimized Die Component Analysis
            die_summary_data = []
            for die_component in fccb_df['Die_Component'].unique():
                die_data = fccb_df[fccb_df['Die_Component'] == die_component]
                die_summary_data.append({
                    'Die_Component': die_component,
                    'Total_Fuses': len(die_data),
                    'HSDs_Affected': die_data['HSD_ID'].nunique(),
                    'Unique_Fuse_Names': die_data['Fuse_Name'].nunique(),
                    'Most_Common_Change': die_data['Change_Reason'].mode().iloc[0] if not die_data['Change_Reason'].empty else ''
                })
            
            die_analysis_df = pd.DataFrame(die_summary_data)
            die_analysis_df.to_excel(writer, sheet_name='Die_Component_Analysis', index=False)
            print(f"   ✅ Die_Component_Analysis sheet: {len(die_analysis_df)} die components")
            
            # Optimized Statistics with vectorized operations
            stats_data = {
                'Metric': [
                    'Total Batches Processed',
                    'Total HSDs Analyzed', 
                    'Total Fuse Changes',
                    'Unique Die Components',
                    'Unique Fuse Names',
                    'Average Fuses per HSD',
                    'Most Common Die Component',
                    'Most Common Change Reason'
                ],
                'Value': [
                    len(all_responses),
                    fccb_df['HSD_ID'].nunique(),
                    len(fccb_df),
                    fccb_df['Die_Component'].nunique(),
                    fccb_df['Fuse_Name'].nunique(),
                    round(len(fccb_df) / fccb_df['HSD_ID'].nunique(), 1),
                    fccb_df['Die_Component'].mode().iloc[0] if not fccb_df['Die_Component'].empty else 'N/A',
                    fccb_df['Change_Reason'].mode().iloc[0] if not fccb_df['Change_Reason'].empty else 'N/A'
                ]
            }
            stats_df = pd.DataFrame(stats_data)
            stats_df.to_excel(writer, sheet_name='Statistics', index=False)
            print(f"   ✅ Statistics sheet: Key metrics from all batches")
        
        # Enhanced final summary with HSD verification
        file_size_kb = round(os.path.getsize(output_excel_file) / 1024, 1)
        unique_hsds = fccb_df['HSD_ID'].unique()
        
        print(f"✅ FCCB Excel file created successfully: {output_excel_file}")
        print(f"   📁 File size: {file_size_kb} KB")
        print(f"   🔢 Total FCCB records: {len(all_fccb_records)}")
        print(f"   🏷️ HSDs processed: {fccb_df['HSD_ID'].nunique()}")
        print(f"   📋 HSD IDs captured: {', '.join(sorted(unique_hsds))}")
        print(f"   🎯 Unique fuse names: {fccb_df['Fuse_Name'].nunique()}")
        print(f"   🎯 Die components: {fccb_df['Die_Component'].nunique()}")
        print(f"   📦 Batches processed: {len(all_responses)}")
        
        # Display processing errors if any
        if processing_errors:
            print(f"\n⚠️ Processing Errors Encountered ({len(processing_errors)}):")
            for error in processing_errors:
                print(f"   • {error}")
        
        # Summary of field standardization
        print(f"\n🔧 Field Standardization Summary:")
        print(f"   • All JSON responses have been standardized to use 'hsd_id' field")
        print(f"   • Any 'id' fields found were automatically converted to 'hsd_id'")
        print(f"   • This ensures consistency across all batch responses")
        
        # Display optimized sample data
        print(f"\n📋 Sample FCCB data preview:")
        preview_columns = ['HSD_ID', 'Fuse_Name', 'Old_Value', 'New_Value', 'Die_Component']
        available_columns = [col for col in preview_columns if col in fccb_df.columns]
        if available_columns:
            print(fccb_df[available_columns].head(3).to_string(index=False, max_colwidth=50))
        
        return str(output_excel_file)
        
    except Exception as e:
        print(f"❌ Error parsing FCCB batch responses to Excel: {e}")
        import traceback
        traceback.print_exc()
        return None


def convert_hsd_data_to_excel(hsd_json_file, output_excel_file):
    """
    Convert HSD JSON data to Excel format with multiple sheets for better organization.
    
    Parameters:
    hsd_json_file (str): Path to the JSON file containing HSD data
    output_excel_file (str): Path for the output Excel file
    
    Returns:
    str: Path to the created Excel file
    """
    try:
        # Ensure output file is in the logs directory
        if not str(output_excel_file).startswith(str(Path("hsd_summary_logs"))):
            output_excel_file = get_log_file_path(Path(output_excel_file).name)
        
        with open(hsd_json_file, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        # Create Excel writer object
        with pd.ExcelWriter(output_excel_file, engine='openpyxl') as writer:
            
            if "data" in json_data and isinstance(json_data["data"], list):
                # Create main HSD data sheet
                hsd_df = pd.json_normalize(json_data["data"])
                
                # Ensure proper column ordering if specific columns exist
                preferred_columns = ['id', 'title', 'description', 'status', 'comments', 'forum_notes']
                existing_columns = [col for col in preferred_columns if col in hsd_df.columns]
                other_columns = [col for col in hsd_df.columns if col not in preferred_columns]
                column_order = existing_columns + other_columns
                
                if column_order:
                    hsd_df = hsd_df[column_order]
                
                hsd_df.to_excel(writer, sheet_name='HSD_Data', index=False)
                
                # Create summary sheet with key statistics
                summary_data = {
                    'Metric': ['Total HSDs', 'Unique Statuses', 'HSDs with Comments', 'HSDs with Descriptions'],
                    'Count': [
                        len(json_data["data"]),
                        len(hsd_df['status'].unique()) if 'status' in hsd_df.columns else 0,
                        len(hsd_df[hsd_df['comments'].notna()]) if 'comments' in hsd_df.columns else 0,
                        len(hsd_df[hsd_df['description'].notna()]) if 'description' in hsd_df.columns else 0
                    ]
                }
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
                
                # If status field exists, create status breakdown sheet
                if 'status' in hsd_df.columns:
                    status_counts = hsd_df['status'].value_counts().reset_index()
                    status_counts.columns = ['Status', 'Count']
                    status_counts.to_excel(writer, sheet_name='Status_Breakdown', index=False)
                
                # Create a simplified view with just ID, Title, and Status (if available)
                simple_columns = []
                if 'id' in hsd_df.columns:
                    simple_columns.append('id')
                if 'title' in hsd_df.columns:
                    simple_columns.append('title')
                if 'status' in hsd_df.columns:
                    simple_columns.append('status')
                
                if simple_columns:
                    simple_df = hsd_df[simple_columns].copy()
                    # Rename columns for better readability
                    column_rename = {'id': 'HSD ID', 'title': 'Title', 'status': 'Status'}
                    simple_df = simple_df.rename(columns=column_rename)
                    simple_df.to_excel(writer, sheet_name='HSD_Simple_View', index=False)
                
                print(f"✅ Excel file created successfully: {output_excel_file}")
                print(f"   • Main data sheet: {len(json_data['data'])} HSD records")
                print(f"   • Summary sheet: Key metrics and statistics")
                if 'status' in hsd_df.columns:
                    print(f"   • Status breakdown sheet: {len(status_counts)} different statuses")
                if simple_columns:
                    print(f"   • Simple view sheet: {len(simple_columns)} key columns")
            else:
                # Handle case where JSON structure is different
                df = pd.json_normalize(json_data)
                df.to_excel(writer, sheet_name='Raw_Data', index=False)
                print(f"✅ Excel file created with raw data: {output_excel_file}")
        
        return str(output_excel_file)
        
    except Exception as e:
        print(f"❌ Error converting to Excel: {e}")
        return None


def parse_hsd_summary_format(content):
    """
    Parse HSD summary content that may be in various formats:
    - New nested JSON format: {"reports": [{"HSD_ID": "...", "Summary": {"Issue": "...", "Status": "...", "Impact": "..."}}]}
    - List format: [{'HSD ID': '16027354779', 'Summary': 'The Supercollider test encounters...'}]
    
    Parameters:
    content (str): The content to parse
    
    Returns:
    pandas.DataFrame: DataFrame with HSD ID and Summary columns, or None if no data found
    """
    try:
        import ast
        
        # First, try to parse the new nested JSON format with reports structure
        json_pattern = r'\{[^{}]*"reports"[^{}]*\[[^\]]*\][^{}]*\}'
        json_matches = re.findall(json_pattern, content, re.DOTALL)
        
        for match in json_matches:
            try:
                # Try to parse as JSON
                data = json.loads(match)
                
                if isinstance(data, dict) and "reports" in data:
                    reports = data["reports"]
                    if isinstance(reports, list) and len(reports) > 0:
                        processed_data = []
                        
                        for report in reports:
                            if isinstance(report, dict):
                                # Look for HSD_ID variations
                                hsd_id = None
                                for key in ['HSD_ID', 'hsd_id', 'HSD ID', 'id']:
                                    if key in report:
                                        hsd_id = str(report[key]).strip()
                                        break
                                
                                # Extract summary information
                                summary_text = "No summary available"
                                if "Summary" in report and isinstance(report["Summary"], dict):
                                    summary_parts = []
                                    summary_obj = report["Summary"]
                                    
                                    if "Issue" in summary_obj:
                                        summary_parts.append(f"Issue: {summary_obj['Issue']}")
                                    if "Status" in summary_obj:
                                        summary_parts.append(f"Status: {summary_obj['Status']}")
                                    if "Impact" in summary_obj:
                                        summary_parts.append(f"Impact: {summary_obj['Impact']}")
                                    
                                    if summary_parts:
                                        summary_text = " | ".join(summary_parts)
                                elif "Summary" in report:
                                    summary_text = str(report["Summary"]).strip()
                                
                                if hsd_id:
                                    processed_data.append({
                                        'HSD ID': hsd_id,
                                        'Summary': summary_text
                                    })
                        
                        if processed_data:
                            print(f"   • Found {len(processed_data)} HSD records in new nested JSON format")
                            return pd.DataFrame(processed_data)
                            
            except json.JSONDecodeError:
                continue
        
        # Look for list patterns in the content (original format)
        list_patterns = [
            r'\[.*?\]',  # Standard list format
            r'\[\s*\{.*?\}\s*\]',  # List with dictionary
        ]
        
        for pattern in list_patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            
            for match in matches:
                try:
                    # Try to safely evaluate the string as a Python literal
                    data = ast.literal_eval(match)
                    
                    if isinstance(data, list) and len(data) > 0:
                        # Check if it's a list of dictionaries with HSD ID and Summary
                        if all(isinstance(item, dict) for item in data):
                            # Look for variations of HSD ID and Summary keys
                            hsd_keys = ['HSD ID', 'hsd_id', 'id', 'HSD_ID', 'HSDID']
                            summary_keys = ['Summary', 'summary', 'SUMMARY', 'description', 'Description']
                            
                            processed_data = []
                            for item in data:
                                hsd_id = None
                                summary = None
                                
                                # Find HSD ID
                                for key in hsd_keys:
                                    if key in item:
                                        hsd_id = str(item[key]).strip()
                                        break
                                
                                # Find Summary
                                for key in summary_keys:
                                    if key in item:
                                        summary = str(item[key]).strip()
                                        break
                                
                                # Include HSDs even if summary is missing or empty
                                if hsd_id:
                                    if not summary or summary == 'None' or summary == '':
                                        summary = 'No summary available'
                                    processed_data.append({
                                        'HSD ID': hsd_id, 
                                        'Summary': summary
                                    })
                            
                            if processed_data:
                                print(f"   • Found {len(processed_data)} HSD records in list format")
                                return pd.DataFrame(processed_data)
                                
                except (ValueError, SyntaxError, TypeError):
                    continue
        
        # If no structured list format found, try to parse individual HSD entries from text
        # Look for patterns like "HSD ID: 12345" followed by content
        hsd_pattern = r"(?:HSD\s*(?:ID|#)?[:\s]*([0-9]+))(.*?)(?=HSD\s*(?:ID|#)?[:\s]*[0-9]+|$)"
        hsd_matches = re.findall(hsd_pattern, content, re.DOTALL | re.IGNORECASE)
        
        if hsd_matches:
            processed_data = []
            for hsd_id, content_block in hsd_matches:
                # Clean up the content block
                content_block = re.sub(r'\s+', ' ', content_block.strip())
                
                # Look for summary-like content
                summary_patterns = [
                    r'(?:Summary|Description|Analysis)[:\s]*(.*?)(?=\n|$)',
                    r'^(.*?)(?:\n|$)'  # Fallback: take first line/sentence
                ]
                
                summary = "No summary available"
                for pattern in summary_patterns:
                    summary_match = re.search(pattern, content_block, re.IGNORECASE)
                    if summary_match:
                        summary = summary_match.group(1).strip()
                        if summary:  # Only use non-empty summaries
                            break
                
                processed_data.append({
                    'HSD ID': hsd_id.strip(),
                    'Summary': summary
                })
            
            if processed_data:
                print(f"   • Found {len(processed_data)} HSD records in text format")
                return pd.DataFrame(processed_data)
        
        print(f"   • No HSD data found in expected format")
        return None
        
    except Exception as e:
        print(f"Error parsing HSD summary format: {e}")
        return None


def create_consolidated_hsd_summary_excel(all_responses, output_excel_file):
    """
    Create a consolidated Excel file with HSD summary data from all batch responses.
    Creates 3 sheets: HSD_Summary, Full_Responses, and Analysis_Statistics.
    
    Parameters:
    all_responses (list): List of response dictionaries from all successful batches
    output_excel_file (str): Path for the output Excel file
    
    Returns:
    str: Path to the created Excel file
    """
    try:
        import pandas as pd
        
        # Ensure output file is in the logs directory
        if not str(output_excel_file).startswith(str(Path("hsd_summary_logs"))):
            output_excel_file = get_log_file_path(Path(output_excel_file).name)
        
        all_hsd_summaries = []
        
        print(f"   • Processing {len(all_responses)} batch responses for consolidated analysis...")
        
        for response in all_responses:
            batch_num = response['batch_num']
            content = response['response']
            batch_file = response['batch_file']
            
            print(f"   • Processing Batch {batch_num} response...")
            
            # Try to parse HSD summary format from each batch response
            hsd_summary_df = parse_hsd_summary_format(content)
            
            if hsd_summary_df is not None and not hsd_summary_df.empty:
                # Add batch number to each HSD record
                hsd_summary_df['Batch'] = batch_num
                hsd_summary_df['Source_File'] = batch_file
                all_hsd_summaries.append(hsd_summary_df)
                print(f"     ✅ Successfully extracted {len(hsd_summary_df)} HSDs from Batch {batch_num}")
            else:
                print(f"     ⚠️  No HSD data extracted from Batch {batch_num}")
                # Let's see what the response looks like for debugging
                print(f"     📝 Response preview: {content[:200]}...")
        
        print(f"   • Total HSDs extracted across all batches: {sum(len(df) for df in all_hsd_summaries)}")
        
        # Create Excel writer object
        with pd.ExcelWriter(output_excel_file, engine='openpyxl') as writer:
            
            # Create consolidated HSD Summary sheet
            if all_hsd_summaries:
                consolidated_hsd_df = pd.concat(all_hsd_summaries, ignore_index=True)
                # Reorder columns for better readability
                column_order = ['HSD ID', 'Summary', 'Batch', 'Source_File']
                existing_columns = [col for col in column_order if col in consolidated_hsd_df.columns]
                other_columns = [col for col in consolidated_hsd_df.columns if col not in column_order]
                final_column_order = existing_columns + other_columns
                
                consolidated_hsd_df = consolidated_hsd_df[final_column_order]
                consolidated_hsd_df.to_excel(writer, sheet_name='HSD_Summary', index=False)
                print(f"   • HSD_Summary sheet: {len(consolidated_hsd_df)} HSD records from all batches")
            else:
                # Create empty sheet with headers for debugging
                empty_df = pd.DataFrame(columns=['HSD ID', 'Summary', 'Batch', 'Source_File'])
                empty_df.to_excel(writer, sheet_name='HSD_Summary', index=False)
                print(f"   • HSD_Summary sheet: 0 HSD records (no data extracted from any batch)")
            
            # Create full responses sheet (for reference)
            full_responses = []
            for response in all_responses:
                full_responses.append({
                    'Batch': response['batch_num'],
                    'Source_File': response['batch_file'],
                    'Output_File': response['output_file'],
                    'Full_Response': response['response']
                })
            
            if full_responses:
                full_df = pd.DataFrame(full_responses)
                full_df.to_excel(writer, sheet_name='Full_Responses', index=False)
                print(f"   • Full_Responses sheet: {len(full_responses)} complete batch responses")
            
            # Create statistics sheet
            if all_hsd_summaries:
                consolidated_hsd_df = pd.concat(all_hsd_summaries, ignore_index=True)
                stats_data = {
                    'Metric': [
                        'Total HSDs Analyzed',
                        'Total Batches Processed',
                        'Batches with Data',
                        'Average HSDs per Batch',
                        'HSDs with Analysis'
                    ],
                    'Count': [
                        len(consolidated_hsd_df),
                        len(all_responses),
                        len(all_hsd_summaries),
                        round(len(consolidated_hsd_df) / len(all_hsd_summaries), 1) if all_hsd_summaries else 0,
                        len(consolidated_hsd_df[consolidated_hsd_df['Summary'].notna()])
                    ]
                }
                stats_df = pd.DataFrame(stats_data)
                stats_df.to_excel(writer, sheet_name='Analysis_Statistics', index=False)
                print(f"   • Analysis_Statistics sheet: Key metrics and statistics")
            else:
                # Create empty stats for debugging
                stats_data = {
                    'Metric': ['Total HSDs Analyzed', 'Total Batches Processed', 'Batches with Data'],
                    'Count': [0, len(all_responses), 0]
                }
                stats_df = pd.DataFrame(stats_data)
                stats_df.to_excel(writer, sheet_name='Analysis_Statistics', index=False)
                print(f"   • Analysis_Statistics sheet: No HSD data to analyze")
        
        print(f"✅ Consolidated HSD summary Excel file created successfully: {output_excel_file}")
        return str(output_excel_file)
        
    except Exception as e:
        print(f"❌ Error creating consolidated HSD summary Excel: {e}")
        return None


def convert_ai_response_to_excel(ai_response_file, output_excel_file):
    """
    Convert AI response text to Excel format by extracting structured information.
    
    Parameters:
    ai_response_file (str): Path to the AI response text file
    output_excel_file (str): Path for the output Excel file
    
    Returns:
    str: Path to the created Excel file
    """
    try:
        # Ensure output file is in the logs directory
        if not str(output_excel_file).startswith(str(Path("hsd_summary_logs"))):
            output_excel_file = get_log_file_path(Path(output_excel_file).name)
        
        with open(ai_response_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        with pd.ExcelWriter(output_excel_file, engine='openpyxl') as writer:
            
            # First, try to parse the specific HSD summary format
            hsd_summary_df = parse_hsd_summary_format(content)
            
            if hsd_summary_df is not None and not hsd_summary_df.empty:
                # Create the main HSD Summary sheet with proper column headers
                hsd_summary_df.to_excel(writer, sheet_name='HSD_Summary', index=False)
                hsd_data_extracted = True
                print(f"   • HSD_Summary sheet: {len(hsd_summary_df)} HSD records with proper column headers")
            
            # Try to extract other structured HSD data (list of dictionaries format)
            else:
                hsd_data_extracted = False
            
            # Look for list patterns like [{'HSD ID': '...', 'Summary': '...'}]
            list_pattern = r'\[.*?\]'
            list_matches = re.findall(list_pattern, content, re.DOTALL)
            
            for i, match in enumerate(list_matches):
                try:
                    # Try to evaluate the list string safely
                    import ast
                    data_list = ast.literal_eval(match)
                    
                    if isinstance(data_list, list) and len(data_list) > 0:
                        if isinstance(data_list[0], dict):
                            # Convert list of dictionaries to DataFrame
                            df = pd.DataFrame(data_list)
                            sheet_name = f'HSD_Analysis_{i+1}' if i > 0 else 'HSD_Analysis'
                            df.to_excel(writer, sheet_name=sheet_name, index=False)
                            hsd_data_extracted = True
                            print(f"   • {sheet_name} sheet: {len(data_list)} HSD records extracted")
                            
                except (ValueError, SyntaxError, TypeError) as e:
                    # If literal_eval fails, skip this match
                    continue
            
            # Try to extract JSON data if present in the response
            json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            json_matches = re.findall(json_pattern, content, re.DOTALL)
            
            for i, json_str in enumerate(json_matches):
                try:
                    json_data = json.loads(json_str)
                    
                    if isinstance(json_data, dict):
                        # Flatten the JSON and create DataFrame
                        df = pd.json_normalize(json_data)
                        sheet_name = f'JSON_Data_{i+1}' if i > 0 else 'JSON_Data'
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                        print(f"   • {sheet_name} sheet: JSON data extracted")
                    
                except json.JSONDecodeError:
                    continue
            
            # Always create a raw text sheet
            lines = content.split('\n')
            text_df = pd.DataFrame({'AI_Response': lines})
            text_df.to_excel(writer, sheet_name='Raw_Response', index=False)
            
            # Try to extract sections based on common AI response patterns
            sections = {}
            current_section = None
            current_content = []
            
            for line in lines:
                line = line.strip()
                if line and (line.isupper() or line.startswith('##') or line.startswith('**')):
                    # Save previous section
                    if current_section:
                        sections[current_section] = '\n'.join(current_content)
                    # Start new section
                    current_section = line.replace('#', '').replace('*', '').strip()
                    current_content = []
                elif line:
                    current_content.append(line)
            
            # Save last section
            if current_section:
                sections[current_section] = '\n'.join(current_content)
            
            # Create sections sheet if sections found
            if sections:
                sections_df = pd.DataFrame(list(sections.items()), columns=['Section', 'Content'])
                sections_df.to_excel(writer, sheet_name='Sections', index=False)
                print(f"   • Sections sheet: {len(sections)} sections extracted")
            
            # If no structured data was found, try to parse key-value pairs manually
            if not hsd_data_extracted:
                hsd_pattern = r"(?:HSD\s*(?:ID|#)?[:\s]*([0-9]+).*?(?:Summary|Description)[:\s]*(.*?)(?=HSD|$))"
                hsd_matches = re.findall(hsd_pattern, content, re.DOTALL | re.IGNORECASE)
                
                if hsd_matches:
                    hsd_list = []
                    for hsd_id, summary in hsd_matches:
                        # Clean up the summary text
                        summary = re.sub(r'\s+', ' ', summary.strip())
                        hsd_list.append({'HSD ID': hsd_id.strip(), 'Summary': summary})
                    
                    if hsd_list:
                        df = pd.DataFrame(hsd_list)
                        df.to_excel(writer, sheet_name='Extracted_HSDs', index=False)
                        print(f"   • Extracted_HSDs sheet: {len(hsd_list)} HSD records extracted from text")
        
        print(f"✅ AI response Excel file created successfully: {output_excel_file}")
        return str(output_excel_file)
        
    except Exception as e:
        print(f"❌ Error converting AI response to Excel: {e}")
        return None


import argparse
import sys

if __name__ == "__main__":
    # Argument parsing
    parser = argparse.ArgumentParser(description="Process query ID or HSD ID for HSD data retrieval.")
    parser.add_argument("--query_id", help="The query ID to fetch HSD data.")
    parser.add_argument("--hsd_id", help="The HSD ID to fetch specific HSD data.")
    parser.add_argument("--user_prompt", required=True, help="Path to the text file containing the user action prompt.")
    parser.add_argument("--output_ext", choices=["text", "html", "json"], default="text", help="The extension of the output file.")
    parser.add_argument("--d", action="store_true", help="Enable debug mode to output prompts to a file.")
    parser.add_argument("--report_formatting", help="Path to the text file containing report formatting prompt instructions.")
    parser.add_argument("--hsd_excel", action="store_true", help="Generate Excel (.xlsx) files in addition to standard output files.")
    parser.add_argument("--ai_excel", action="store_true", help="Generate Excel (.xlsx) files of AI response in addition to standard output files.")

    args = parser.parse_args()

    # Check for conflicting arguments
    if args.query_id and args.hsd_id:
        print("Error: You cannot specify both --query_id and --hsd_id at the same time.")
        sys.exit(1)

    #Read the user action prompt from the specified file
    try:
        with open(args.user_prompt, 'r', encoding='utf-8') as prompt_file:
            user_action_prompt = prompt_file.read().strip()
    except FileNotFoundError:
        print(f"Error: The file '{args.user_prompt}' was not found.")
        exit(1)
    except Exception as e:
        print(f"An error occurred while reading the user prompt file: {e}")
        exit(1)

    # Read the report formatting from the specified file
    report_formatting = ""
    if args.report_formatting:
        try:
            with open(args.report_formatting, 'r', encoding='utf-8') as format_file:
                report_formatting = format_file.read().strip()
        except FileNotFoundError:
            print(f"Error: The file '{args.report_formatting}' was not found.")
            exit(1)
        except Exception as e:
            print(f"An error occurred while reading the report formatting file: {e}")
            exit(1)

    # Set the output_ext based on the output_format
    if args.output_ext == "text":
        output_ext = "Report the output in text format."
    elif args.output_ext == "html":
        output_ext = "Report the output ONLY in nicely formatted list in HTML format. Do not provide any preamble text."
    elif args.output_ext == "json":
        output_ext = "Report the output ONLY in nicely formatted JSON. Do not provide any preamble text."

    # Append the output_ext to the user_action_prompt
    user_action_prompt = user_action_prompt + "\n" + report_formatting + "\n" + output_ext
    #user_action_prompt = "\n" + report_formatting + "\n" + output_ext
    #system_prompt = "You are a Intel SoC Validation assistant. You need to analyse the data from the system validation point of view and provide the response to help engineers improve validation."
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
    hsd_connector = HsdConnector()
    openai_connector = OpenAIConnector()
    
    if args.query_id:
        # Fetch all HSD IDs from the query
        hsd_ids = hsd_connector.fetch_hsd_ids_from_query(args.query_id)
        print(f"hsd_ids: {len(hsd_ids)} HSDs found")
        
        if not hsd_ids:
            print("Failed to fetch HSD IDs.")
            sys.exit(1)
        else:
            # Process HSDs in batches to avoid token limits
            batch_files = hsd_connector.get_multiple_hsd_data_in_batch(hsd_ids, batch_size=3)
            
            # Process each batch file with OpenAI
            all_responses = []
            
            for batch_num, batch_file in enumerate(batch_files, 1):
                print(f"\n🤖 Processing Batch {batch_num}/{len(batch_files)} with OpenAI...")
                
                try:
                    res = openai_connector.run_prompt_with_json(batch_file, system_prompt, user_action_prompt)
                    
                    # Create output filename for this batch
                    base_filename = Path(batch_file).stem
                    timestamp = base_filename.split('_')[-1]
                    new_base_filename = '_'.join(base_filename.split('_')[:-1]) + '_gpt_output_' + timestamp
                    
                    # Determine file extension
                    response_format = args.output_ext
                    extension = ".txt" if response_format == "text" else ".html" if response_format == "html" else ".json"
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
                    
                    print(f"  ✅ Batch {batch_num} response saved to: {batch_output_filename}")
                    
                    # Convert to Excel per batch if --hsd_excel is specified
                    if args.hsd_excel:
                        print(f"  📊 Creating individual Excel files for batch {batch_num}...")
                        hsd_excel_filename = get_log_file_path(f"{Path(batch_file).stem}.xlsx")
                        convert_hsd_data_to_excel(batch_file, str(hsd_excel_filename))
                
                except Exception as e:
                    print(f"  ❌ Error processing batch {batch_num}: {e}")
                    all_responses.append({
                        'batch_num': batch_num,
                        'batch_file': batch_file,
                        'error': str(e)
                    })
            
            # Create a combined summary report
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            summary_filename = get_log_file_path(f"batch_processing_summary_{args.query_id}_{timestamp}.txt")
            
            with open(summary_filename, "w", encoding='utf-8') as summary_file:
                summary_file.write(f"BATCH PROCESSING SUMMARY\n")
                summary_file.write(f"========================\n\n")
                summary_file.write(f"Query ID: {args.query_id}\n")
                summary_file.write(f"Total HSDs: {len(hsd_ids)}\n")
                summary_file.write(f"Total Batches: {len(batch_files)}\n")
                summary_file.write(f"Batch Size: 10 HSDs per batch\n")
                summary_file.write(f"Processing Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                successful_batches = [r for r in all_responses if 'error' not in r]
                failed_batches = [r for r in all_responses if 'error' in r]
                
                summary_file.write(f"RESULTS:\n")
                summary_file.write(f"  • Successful Batches: {len(successful_batches)}\n")
                summary_file.write(f"  • Failed Batches: {len(failed_batches)}\n\n")
                
                summary_file.write(f"BATCH DETAILS:\n")
                for response in all_responses:
                    if 'error' not in response:
                        summary_file.write(f"  ✅ Batch {response['batch_num']}: {response['output_file']}\n")
                    else:
                        summary_file.write(f"  ❌ Batch {response['batch_num']}: {response['error']}\n")
            
            print(f"\n📊 PROCESSING COMPLETE!")
            print(f"Summary report: {summary_filename}")
            print(f"Successful batches: {len(successful_batches)}/{len(batch_files)}")
            
            # Create consolidated Excel files based on user requirements
            consolidated_hsd_excel = None
            consolidated_ai_excel = None
            
            if args.hsd_excel:
                print(f"\n📊 Creating consolidated HSD Excel file...")
                
                # Create consolidated HSD data Excel file
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                consolidated_hsd_excel = get_log_file_path(f"consolidated_hsd_data_{args.query_id}_{timestamp}.xlsx")
                
                try:
                    # Combine all HSD data from successful batches
                    all_hsd_data = {"data": []}
                    for batch_file in batch_files:
                        try:
                            with open(batch_file, 'r', encoding='utf-8') as f:
                                batch_data = json.load(f)
                                if "data" in batch_data and isinstance(batch_data["data"], list):
                                    all_hsd_data["data"].extend(batch_data["data"])
                        except Exception as e:
                            print(f"  ⚠️  Warning: Could not read batch file {batch_file}: {e}")
                    
                    # Save consolidated HSD data to temporary JSON and convert to Excel
                    temp_hsd_json = get_log_file_path(f"temp_consolidated_hsd_{timestamp}.json")
                    with open(temp_hsd_json, 'w', encoding='utf-8') as f:
                        json.dump(all_hsd_data, f, indent=4, ensure_ascii=False)
                    
                    convert_hsd_data_to_excel(temp_hsd_json, consolidated_hsd_excel)
                    os.remove(temp_hsd_json)  # Clean up temporary file
                    print(f"  ✅ Consolidated HSD Excel: {consolidated_hsd_excel}")
                    
                except Exception as e:
                    print(f"  ❌ Error creating consolidated HSD Excel file: {e}")
            
            if args.ai_excel:
                print(f"\n📊 Creating consolidated AI Analysis Excel file...")
                
                # Create consolidated AI analysis Excel with HSD summary
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                consolidated_ai_excel = get_log_file_path(f"consolidated_ai_responses_{args.query_id}_{timestamp}.xlsx")
                
                try:
                    result_excel = parse_fccb_json_to_excel(successful_batches, consolidated_ai_excel)
                    #create_consolidated_hsd_summary_excel(successful_batches, consolidated_ai_excel)
                    print(f"  ✅ Consolidated AI Analysis Excel: {consolidated_ai_excel}")
                    
                except Exception as e:
                    print(f"  ❌ Error creating consolidated AI Analysis Excel file: {e}")
            
            # Set the main variables for final output (use first batch for compatibility)
            hsd_query_data_file = batch_files[0] if batch_files else None
            openai_output_filename = all_responses[0]['output_file'] if successful_batches else None

    
    elif args.hsd_id:
        hsd_query_data_file = hsd_connector.get_hsd_data_in_file(args.hsd_id)
        if hsd_query_data_file is None:
            print("Failed to fetch query data.")
            sys.exit(1)

        try:
            res = openai_connector.run_prompt_with_json(hsd_query_data_file, system_prompt, user_action_prompt)

            # Determine the file extension based on the output format
            response_format = args.output_ext
            extension = ".txt" if response_format == "text" else ".html" if response_format == "html" else ".json"
            # Modify the filename to include '_OpenAI_OUTPUT_' before the timestamp
            base_filename = Path(hsd_query_data_file).stem  # Get the base filename without extension
            timestamp = base_filename.split('_')[-1]  # Extract the timestamp
            new_base_filename = '_'.join(base_filename.split('_')[:-1]) + '_gpt_output_' + timestamp  # Construct new base filename
            openai_output_filename = get_log_file_path(new_base_filename + extension)

            with open(openai_output_filename, "w", encoding='utf-8') as file:
                file.write(res['response'])
            
            print(f"🤖 OpenAI response saved to: {openai_output_filename}")
            # Convert both HSD JSON data and AI response to Excel format (if requested)
            if args.hsd_excel:
                print("\n📊 Converting data to Excel format...")

                # Convert HSD JSON data to Excel
                hsd_excel_filename = get_log_file_path(f"{Path(hsd_query_data_file).stem}.xlsx")
                hsd_excel_file = convert_hsd_data_to_excel(hsd_query_data_file, str(hsd_excel_filename))
                
                # # Convert HSD JSON data to Excel
                # hsd_excel_filename = get_log_file_path(f"{Path(hsd_query_data_file).stem}.xlsx")
                # hsd_excel_file = convert_hsd_data_to_excel(hsd_query_data_file, str(hsd_excel_filename))
            if args.ai_excel:  
                # Convert AI response to Excel
                ai_excel_filename = get_log_file_path(f"consolidated_ai_responses_{args.hsd_id}_{timestamp}.xlsx")
                ai_excel_file = convert_ai_response_to_excel(str(openai_output_filename), str(ai_excel_filename))
            else:
                hsd_excel_file = None
                ai_excel_file = None

        except Exception as e:
            print(f"❌ Error in single file processing: {e}")

    else:
        print("Error: You must provide either --query_id or --hsd_id.")
        sys.exit(1)
            
    # Display the filename in yellow and bold
    YELLOW_BOLD = '\033[1;93m'
    GREEN_BOLD = '\033[1;92m'
    RESET = '\033[0m'
    
    # Display Excel file information
    if args.hsd_excel and args.hsd_id:
        if 'hsd_excel_file' in locals() and hsd_excel_file:
            print(f"HSD data Excel file: {GREEN_BOLD}{hsd_excel_file}{RESET}")
    if args.ai_excel and args.hsd_id:
        if 'ai_excel_file' in locals() and ai_excel_file:
            print(f"AI response Excel file: {GREEN_BOLD}{ai_excel_file}{RESET}")

    if args.hsd_excel and args.query_id:
        if 'consolidated_hsd_excel' in locals() and consolidated_hsd_excel:
            print(f"Consolidated HSD data Excel file: {GREEN_BOLD}{consolidated_hsd_excel}{RESET}")
    if args.ai_excel and args.query_id:
        if 'consolidated_ai_excel' in locals() and consolidated_ai_excel:
            print(f"Consolidated AI Analysis Excel file: {GREEN_BOLD}{consolidated_ai_excel}{RESET}")
    
    # Display tips only if no Excel files were generated
    if not args.hsd_excel and not args.ai_excel:
        print(f"\n💡 Tip: Use --hsd_excel flag to also generate Excel (.xlsx) files for easier data analysis!")
        print(f"💡 Tip: Use --ai_excel flag to also generate Excel (.xlsx) files for AI response analysis!")

    print("\nProcessing complete.")