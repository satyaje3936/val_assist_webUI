import requests
import urllib3
import http.client
import traceback
from datetime import datetime
import json
from requests_kerberos import HTTPKerberosAuth
import logging
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '../', 'common'))
from common.logging_config import logger

requests.packages.urllib3.disable_warnings()

class HsdConnector:
    # CLEANUP (vbbhogad) - Lot of deadcode here needs to be cleaned. up. The whole HSD connector eventually needs to move to another file as these classes will be used in other script.

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
                 logger.error('Got "urllib3.exceptions.MaxRetryError" exception, retrying {} more attempts'.format(retry - 1))
                 retry -= 1
             except requests.exceptions.ProxyError:
                 logger.error('Got "requests.exceptions.ProxyError" exception, retrying {} more attempts'.format(retry - 1))
                 retry -= 1
             except http.client.RemoteDisconnected:
                 logger.error('Got "http.client.RemoteDisconnected" exception, retrying {} more attempts'.format(retry - 1))
                 retry -= 1
             except Exception as e:
                 logger.error('Got unknown exception: {}, retrying {} more attempts'.format(traceback.format_exc(), (retry - 1)))
                 retry -= 1

    def get_hsd_links(self, hsd_id, fields=""):
        """
                    Fetches detailed information about all of an HSD page's linked articles using its ID. The method sends a
                    GET request to the HSD API and retrieves the data associated with the given ID. The data is returned as
                    a dictionary.

                    Note: The HSD API requires Kerberos authentication. Meaning it can only be executed locally and not over cloud.

                    Parameters:
                    id (str): The ID of the HSD page to fetch information for.
                    fields (List<str>): fields to include in the response, list of strings (optional)

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
                    :return:json of all the fields for all the linked articles returned from the given hsd
            """

        retry = 10
        while (retry > 0):
            try:
                req = "https://hsdes-api.intel.com/rest/article/" + str(hsd_id) + "/links"
                if len(fields) > 0:
                    req += "?fields=" + str(fields[0])
                    for i in range(len(fields) - 1):
                        req += "%2C%20" + str(fields[i + 1])
                    req += "&showHidden=Y&showDeleted=N"
                headers = {'Content-type': 'application/json'}
                # print req
                response_data = self._get_response(req, headers)
                if "responses" in response_data:
                    return response_data
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
        response = requests.get(req, auth=HTTPKerberosAuth(), verify=False , headers=headers)
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

    def display_hsd_query_fields(self, full_response_data):
        if "data" in full_response_data and isinstance(full_response_data["data"], list) and full_response_data["data"]:
            field_keys = full_response_data["data"][0].keys()
            newline_separator = '\n '
            logger.info(f"The provide query is fetching these HSD fields: {newline_separator.join(field_keys)}")

    def fetch_query_data(self, query_id):

        # Construct the URL dynamically
        base_url = "https://hsdes-api.intel.com/rest/query/execution/"
        req = f"{base_url}{query_id}"
        headers = {'Content-type': 'application/json'}
        response_data = self._get_response(req, headers)
        try:
            # Extract the total number of HSDs
            total_hsds = response_data.get("total", 0)
            if (total_hsds > 0):
                logger.info(f"Total HSD records being processed: {total_hsds}")

                # Construct the updated URL with max_results parameter
                full_query_url = f"{req}?max_results={total_hsds}"
                # print(f"Fetching full data from: {full_query_url}")

                # Fetch full data
                full_response_data = self._get_response(full_query_url, headers)

                self.display_hsd_query_fields(full_response_data)

                return full_response_data
            else:
                logger.info("No HSD entries found.")

        except Exception as e:
            logger.error("An error occurred:", e)

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
                # timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                # hsd_query_data_file = f"hsd_query_{query_id}_{timestamp}.json"
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
                                # Debug: Show status of each HSD
                                for hsd_data in response_data["data"]:
                                    hsd_status = hsd_data.get('status', 'Unknown')
                                    print(f"    ✅ HSD {hsd_id} - Status: {hsd_status}")
                            else:
                                batch_data["data"].append(response_data["data"])
                                # Debug: Show status of the HSD
                                hsd_status = response_data["data"].get('status', 'Unknown')
                                print(f"    ✅ HSD {hsd_id} - Status: {hsd_status}")
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
            with open(batch_file, 'w', encoding='utf-8') as f:
                json.dump(batch_data, f, indent=4, ensure_ascii=False)
            
            batch_files.append(batch_file)
            
            # Show status distribution for this batch
            status_counts = {}
            for hsd_data in batch_data["data"]:
                status = hsd_data.get('status', 'Unknown')
                status_counts[status] = status_counts.get(status, 0) + 1
            
            print(f"  ✅ Batch {batch_num} complete:")
            print(f"    • Successful: {successful_count}")
            print(f"    • Failed: {failed_count}")
            print(f"    • HSDs with content: {len(batch_data['data'])}")
            print(f"    • Status distribution: {dict(status_counts)}")
            print(f"    • Saved to: '{batch_file}'")
        
        # Calculate overall status distribution across all batches
        overall_status_counts = {}
        total_hsds_processed = 0
        
        for batch_file in batch_files:
            try:
                with open(batch_file, 'r', encoding='utf-8') as f:
                    batch_data = json.load(f)
                    if "data" in batch_data:
                        for hsd_data in batch_data["data"]:
                            status = hsd_data.get('status', 'Unknown')
                            overall_status_counts[status] = overall_status_counts.get(status, 0) + 1
                            total_hsds_processed += 1
            except Exception as e:
                print(f"  ⚠️ Warning: Could not read {batch_file} for status summary: {e}")
        
        print(f"\n📊 All Batches Complete:")
        print(f"  • Total batches: {len(batches)}")
        print(f"  • Batch files created: {len(batch_files)}")
        print(f"  • Total HSDs processed: {total_hsds_processed}")
        print(f"  • Overall status distribution: {dict(overall_status_counts)}")
        
        # Specifically highlight rejected HSDs if any
        rejected_count = overall_status_counts.get('rejected', 0)
        if rejected_count > 0:
            print(f"  ✅ Rejected HSDs included: {rejected_count} (These WILL be analyzed)")
        
        return batch_files

