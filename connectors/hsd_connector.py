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
