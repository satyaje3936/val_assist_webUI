from openai import AzureOpenAI
import requests
import httpx
import openai
import urllib3
import http.client
import traceback
import pprint
import os
import sys
import random
import time
import json
import threading
import ast
from datetime import datetime
from pathlib import Path
from requests_kerberos import HTTPKerberosAuth
import argparse
import tiktoken
import logging
sys.path.append(os.path.join(os.path.dirname(__file__), '../', 'common'))
#from logging_config import logger
import logging
logger = logging.getLogger(__name__)


# Get token from environ if available (and not hardcoded above)
if "OPENAI_KEY" in os.environ:
    openai_key = os.environ["OPENAI_KEY"]
# backwards compatibility with lowercase key as older versions of this connector used it like that
elif "openai_key" in os.environ:
    openai_key = os.environ["openai_key"]
else:
    logger.error("Please set an openAI key with environment variable 'OPENAI_KEY'")
    logger.info('''\nINFO - In order to get your openAI key follow these steps:
    1. Register for iVE GenAI Hackathon at https://forms.microsoft.com/Pages/ResponsePage.aspx?id=iI3JRkTj1E6Elk7XcS4lXclO-okE9hFNszyNpymG1CFURVNDOE1LTTRYRFRWNzE5VjI1RkJWQTk1US4u
    2. Go to https://valgpt-api.laas.intel.com/
    3. Select product 'genAi-hackaton'
    4. Click on button "Create New"
    5. Enter a key name to use. This is for your own tracking. i.e., 'iVE Hackaton Key'
    6. Copy and save the generated key. You won't be able to see it later.
    7. Export your key to environment variable 'OPENAI_KEY'
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

class OpenAIConnector:
    # Initialize the OpenAI connector class
    def __init__(self, deployment_name=None):
        if (deployment_name is None):
            deployment_name = DEFAULT_DEPLOYMENT_NAME
        self.deployment_name = deployment_name
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_hsds_processed = 0
        self.finish_reason = ""

    def estimate_token_count(self, messages):
        """
        Estimate the token count for the given messages.
        """
        encoding = tiktoken.encoding_for_model(self.deployment_name)
        num_tokens = 0
        for message in messages:
            num_tokens += len(encoding.encode(message["content"]))
        return num_tokens

    # Run the prompt on the OpenAI model
    def run_prompt(self, prompt):
        '''
        See documentation at
            https://platform.openai.com/docs/guides/text-generation/chat-completions-api
            https://platform.openai.com/docs/api-reference/chat/create
        '''
        # Estimate tokens before running the prompt
        estimated_tokens = self.estimate_token_count(prompt)
        logger.info(f"Estimated tokens before run_prompt: {estimated_tokens}")

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

        # Update token counts
        self.total_prompt_tokens += completion.usage.prompt_tokens
        self.total_completion_tokens += completion.usage.completion_tokens
        self.total_hsds_processed += 1

        logger.info(f" Prompt tokens: {prompt_tokens} | Completion tokens: {completion_tokens} | Total tokens: {total_tokens} | Time taken: {time_taken:.2f} seconds")

        gpt_completion = completion.choices[0].message.content
        return {
            "response": gpt_completion
        }

    
    def run_system_user_prompt(self, system_prompt, user_prompt):
        """
        Run the system and user prompts on the OpenAI model and return the completion message content.
        
        Args:
            system_prompt (str): The system prompt to provide context to the model.
            user_prompt (str): The user prompt to provide the query to the model.
        
        Returns:
            str: The completion message content from the model.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # Estimate tokens before running the prompt
        estimated_tokens = self.estimate_token_count(messages)
        logger.info(f"Estimated tokens before run_system_user_prompt: {estimated_tokens}")
        
        # Record the start time
        start_time = time.time()
        
        completion = client.chat.completions.create(
            model=self.deployment_name,
            messages=messages
        )
        
        # Record the end time
        end_time = time.time()
        
        # Calculate the time taken for the query
        time_taken = end_time - start_time
        
        # Display tokens consumed after completion is received
        prompt_tokens = completion.usage.prompt_tokens
        completion_tokens = completion.usage.completion_tokens
        total_tokens = completion.usage.total_tokens
        finish_reason = completion.choices[0].finish_reason
        
        # Update token counts
        self.total_prompt_tokens += completion.usage.prompt_tokens
        self.total_completion_tokens += completion.usage.completion_tokens
        self.total_hsds_processed += 1
        
        logger.info(f" Prompt tokens: {prompt_tokens} | Completion tokens: {completion_tokens} | Total tokens: {total_tokens} | Time taken: {time_taken:.2f} seconds | Finish reason: {finish_reason}")
        if finish_reason == "length":
            logger.warning("WARNING: The completion was stopped due to reaching the maximum token limit.")
        
        # Log the entire JSON response in DEBUG mode
        #logger.debug(f"Completion JSON: {json.dumps(completion, indent=4)}")
        
        gpt_completion = completion.choices[0].message.content
        return gpt_completion

    def run_prompt_with_json(self, hsd_query_data_file, system_prompt, user_action_prompt):
        try:
            with open(hsd_query_data_file, 'r') as f:
                json_data = json.load(f)
                json_data_str = json.dumps(json_data, indent=4)
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_action_prompt + "/n" + json_data_str},
                ]
                return self.run_prompt(messages)
        except FileNotFoundError:
            logger.error(f"Error: File not found at '{hsd_query_data_file}'. Please check the file path.")
        except json.JSONDecodeError:
            logger.error("Error: Failed to decode JSON. Ensure the file contains valid JSON.")
        except Exception as e:
            logger.error(f"An unexpected error has occurred: {e}")


    def run_prompt_on_the_hsd_data(self, hsd_id, system_prompt, concatened_user_prompt_with_item, response_format_schema):
        # Record the start time
        start_time = time.time()
        #logger.info(f"Querying openAI with HSD ID: {hsd_id}")
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": concatened_user_prompt_with_item}
        ]
        
        if response_format_schema:
            completion = client.chat.completions.create(
                model=DEFAULT_DEPLOYMENT_NAME,
                messages=messages,
                response_format=response_format_schema
            )
        else:
            completion = client.chat.completions.create(
                model=DEFAULT_DEPLOYMENT_NAME,
                messages=messages
            )

        # Record the end time
        end_time = time.time()

        # Calculate the time taken for the query
        time_taken = end_time - start_time

        # Display tokens consumed after completion is received
        prompt_tokens = completion.usage.prompt_tokens
        completion_tokens = completion.usage.completion_tokens
        total_tokens = completion.usage.total_tokens

        logger.info(f"HSD ID: {hsd_id} | Prompt tokens: {prompt_tokens} | Completion tokens: {completion_tokens} | Total tokens: {total_tokens} | Time taken: {time_taken:.2f} seconds")

        # Update token counts
        self.total_prompt_tokens += completion.usage.prompt_tokens
        self.total_completion_tokens += completion.usage.completion_tokens
        self.total_hsds_processed += 1

        return completion.choices[0].message.content if not response_format_schema else completion.choices[0].message
    
    def process_hsd_entry(self, hsd_id, system_prompt, concatened_user_prompt_with_item, response_format_schema):
    # Convert the item to a string if needed
        #query = json.dumps(item)
        # Run the prompt with the JSON data
        response = self.run_prompt_on_the_hsd_data(hsd_id, system_prompt, concatened_user_prompt_with_item, response_format_schema)
        # Process the response
        if response_format_schema:
            # If response_format_schema is provided, response is expected to be a JSON object
            response_json = json.loads(response.content)
        else:
            # If response_format_schema is not provided, response is expected to be a string
            response_json = {"response": response}
        
        return response_json

    def get_token_usage(self):
        return {
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_hsds_processed": self.total_hsds_processed,
            "grand_total_tokens": self.total_prompt_tokens + self.total_completion_tokens
        }
