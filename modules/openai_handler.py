from bigtree import levelorder_iter, tree_to_nested_dict
from threading import Thread
from queue import Queue
import connectors.openai_connector as Openai
import time
import json

text_template = ["The templates contain the fields that must have the input data and a short description of what must have each field.\n",
                 "Fields with '*' in the name are mandatory\n",
                 "You have to check the provided data, check wether the contents from the descriptions are identical to the template provided and return the percentage of matching content with the template\, if a field in the description does not match with the field in the template, return a 0%. If it is included, check if the information has enough content for the user to be understandable\n",
                 "You have to list the fields of the correct template\n",
                 "You have to be compliant with the following statements:\n",
                 "Create a json using the field names from the corresponding template as 1rst level tags, this is a standard.\n",
                 "Each field tag in json must contain 'compliance': percentage and 'suggestion': string, as 2nd level tags.\n",
                 "json must be filled with the information from the provided data and missing fields filled with compliance 0 and a missing message as suggestion.\n",
                 "if there is any missing field in provided data, then try to classify data based in template descriptions.\n",
                 "Add another 1srt level tag 'template': selected template abreviation ( TC for Test Case, TCD for Test Case Definition, TCC for Test Content, TP for Test Plan, TPF for Test Plan Definition)\n",
                 "Add another 1srt level tag 'compliant_avrg':  value (average percentage only of mandatory fields compliant percentages with the template)\n",
                 "Print the selected template fields as a bullet list\n",
                 "Print the json in json with format ```json json_structure ```\n",
                 "json requirements are the most important to comply\n"]

class OpenAIHandler():
    def __init__(self) -> None:
        self.openai = Openai.OpenAIConnector()

    def check_template(self, templates: dict, desc: str, log=False, parallel=False) -> str:
            system_msg = "You are a system validation engineer and need to review your test plan is well documented.\n"
            system_msg += f"This is your Test Plan template {templates['tp']}\n"
            system_msg += f"This is your Test Plan Feature template {templates['tp']}\n"
            system_msg += f"This is your Test Case Description template {templates['tcd']}\n"
            system_msg += f"This is your Test Case template {templates['tc']}\n"
            system_msg += f"This is your Test Content template {templates['content']}\n\n"
            constant_text = ""
            for sentence in text_template:
                constant_text += sentence
            system_msg += constant_text
            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": desc}
            ]
            if log:
                with open('openia.log', 'w') as file:
                    if parallel:
                        response = self.openai.run_prompt_parallel(messages)['response']
                    else:
                        response = self.openai.run_prompt(messages)['response']
                    # json_data = self.wiki.get_text_between(response, '```json', '```')
                    file.write(response)
                    # return json.loads(json_data)
                    return response
            else: 
                if parallel:
                    response = self.openai.run_prompt_parallel(messages)['response']
                else:
                    response = self.openai.run_prompt(messages)['response']
                # json_data = self.wiki.get_text_between(response, '```json', '```')
                # return json.loads(json_data)
                return response

    def check_template_tp(self, templates: dict, desc: str, log=False, parallel=False) -> str:
            system_msg = "You are a system validation engineer and need to review your test plan is well documented.\n"
            system_msg += f"This is your Test Plan template {templates['tp']}\n"
            constant_text = ""
            for sentence in text_template:
                constant_text += sentence
            system_msg += constant_text
            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": desc}
            ]
            if log:
                with open('openia.log', 'w') as file:
                    if parallel:
                        response = self.openai.run_prompt_parallel(messages)['response']
                    else:
                        response = self.openai.run_prompt(messages)['response']
                    # json_data = self.wiki.get_text_between(response, '```json', '```')
                    file.write(response)
                    # return json.loads(json_data)
                    return response
            else: 
                if parallel:
                    response = self.openai.run_prompt_parallel(messages)['response']
                else:
                    response = self.openai.run_prompt(messages)['response']
                # json_data = self.wiki.get_text_between(response, '```json', '```')
                # return json.loads(json_data)
                return response
            
    def check_template_tpf(self, templates: dict, desc: str, log=False, parallel=False) -> str:
            system_msg = "You are a system validation engineer and need to review your test plan is well documented.\n"
            system_msg += f"This is your Test Plan Feature template {templates['tp']}\n"
            constant_text = ""
            for sentence in text_template:
                constant_text += sentence
            system_msg += constant_text
            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": desc}
            ]
            if log:
                with open('openia.log', 'w') as file:
                    if parallel:
                        response = self.openai.run_prompt_parallel(messages)['response']
                    else:
                        response = self.openai.run_prompt(messages)['response']
                    # json_data = self.wiki.get_text_between(response, '```json', '```')
                    file.write(response)
                    # return json.loads(json_data)
                    return response
            else: 
                if parallel:
                    response = self.openai.run_prompt_parallel(messages)['response']
                else:
                    response = self.openai.run_prompt(messages)['response']
                # json_data = self.wiki.get_text_between(response, '```json', '```')
                # return json.loads(json_data)
                return response

    def check_template_tcd(self, templates: dict, desc: str, log=False, parallel=False) -> str:
            system_msg = "You are a system validation engineer and need to review your test plan is well documented.\n"
            system_msg += f"This is your Test Case Description template {templates['tcd']}\n"
            constant_text = ""
            for sentence in text_template:
                constant_text += sentence
            system_msg += constant_text
            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": desc}
            ]
            if log:
                with open('openia.log', 'w') as file:
                    if parallel:
                        response = self.openai.run_prompt_parallel(messages)['response']
                    else:
                        response = self.openai.run_prompt(messages)['response']
                    # json_data = self.wiki.get_text_between(response, '```json', '```')
                    file.write(response)
                    # return json.loads(json_data)
                    return response
            else: 
                if parallel:
                    response = self.openai.run_prompt_parallel(messages)['response']
                else:
                    response = self.openai.run_prompt(messages)['response']
                # json_data = self.wiki.get_text_between(response, '```json', '```')
                # return json.loads(json_data)
                return response

    def check_template_tc(self, templates: dict, desc: str, log=False, parallel=False) -> str:
            system_msg = "You are a system validation engineer and need to review your test plan is well documented.\n"
            system_msg += f"This is your Test Case template {templates['tc']}\n"
            constant_text = ""
            for sentence in text_template:
                constant_text += sentence
            system_msg += constant_text
            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": desc}
            ]
            if log:
                with open('openia.log', 'w') as file:
                    if parallel:
                        response = self.openai.run_prompt_parallel(messages)['response']
                    else:
                        response = self.openai.run_prompt(messages)['response']
                    # json_data = self.wiki.get_text_between(response, '```json', '```')
                    file.write(response)
                    # return json.loads(json_data)
                    return response
            else: 
                if parallel:
                    response = self.openai.run_prompt_parallel(messages)['response']
                else:
                    response = self.openai.run_prompt(messages)['response']
                # json_data = self.wiki.get_text_between(response, '```json', '```')
                # return json.loads(json_data)
                return response


    def check_template_tcc(self, templates: dict, desc: str, log=False, parallel=False) -> str:
            system_msg = "You are a system validation engineer and need to review your test plan is well documented.\n"
            system_msg += f"This is your Test Content template {templates['content']}\n\n"
            constant_text = ""
            for sentence in text_template:
                constant_text += sentence
            system_msg += constant_text
            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": desc}
            ]
            if log:
                with open('openia.log', 'w') as file:
                    if parallel:
                        response = self.openai.run_prompt_parallel(messages)['response']
                    else:
                        response = self.openai.run_prompt(messages)['response']
                    # json_data = self.wiki.get_text_between(response, '```json', '```')
                    file.write(response)
                    # return json.loads(json_data)
                    return response
            else: 
                if parallel:
                    response = self.openai.run_prompt_parallel(messages)['response']
                else:
                    response = self.openai.run_prompt(messages)['response']
                # json_data = self.wiki.get_text_between(response, '```json', '```')
                # return json.loads(json_data)
                return response

    def __rename_key(self, dictionary, old_key, new_key):
        if isinstance(dictionary, dict):
            for key in list(dictionary.keys()):
                if key == old_key:
                    dictionary[new_key] = dictionary.pop(old_key)
                self.__rename_key(dictionary[key], old_key, new_key)
        elif isinstance(dictionary, list):
            for item in dictionary:
                self.__rename_key(item, old_key, new_key)
        
        return dictionary
    
    def hsd_openai_tree_iterate(self, nodo_raiz, templates):
        template_function = {
            "test_plan": self.check_template_tp,
            "test_plan_feature": self.check_template_tpf,
            "test_case_definition": self.check_template_tcd,
            "test_case": self.check_template_tc,
            "test_content": self.check_template_tcc
        }
        
        template_abbrev = {
            "test_plan": "TP",
            "test_plan_feature": "TPF",
            "test_case_definition": "TCD",
            "test_case": "TC",
            "test_content": "TCC"
        }
        def worker():
            while True:
                nodo = q.get()
                if nodo is None:
                    break  # This will stop the loop if there's a None in the queue

                description = ''
                openai_response = {}
                if nodo.get_attr("report") is None or nodo.get_attr("report") == '':
                    nodo.set_attrs({"report": {'error' : 'No description', 'compliant_avrg' : 0, 'template': template_abbrev.get(nodo.get_attr("subject"), None)}})
                elif nodo.get_attr("report") == '[NOT OWNED]':
                    nodo.set_attrs({"report": {'error' : 'Not Owned', 'template': template_abbrev.get(nodo.get_attr("subject"), None)}})
                else:
                    description = nodo.get_attr("report")
                    # print(f'Running OPEN AI FOR {nodo.get_attr("subject")}')
                    time.sleep(0.01)
                    openai_response = template_function[nodo.get_attr("subject")](templates, description, True)
                    report = self.parse_json_from_str(openai_response)
                    report['template'] = template_abbrev.get(nodo.get_attr("subject"), None)
                    nodo.set_attrs({"report": report})
                    # print(openai_response)
                    # print(self.get_text_between(openai_response, '```json', '```'))

                q.task_done()

        q = Queue()
        num_worker_threads = 10  # You can adjust the number of threads
    
        # Enqueue all the nodes
        for nodo in levelorder_iter(nodo_raiz):
            q.put(nodo)
    
        # Stop workers
        for i in range(num_worker_threads):
            q.put(None)


        threads = []
        for i in range(num_worker_threads):
            t = Thread(target=worker)
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        node_dict = tree_to_nested_dict(nodo_raiz, all_attrs=True)
        return node_dict
    """
    def hsd_openai_tree_iterate(self, nodo_raiz, templates):
        template_function = {
            "test_plan":self.check_template_tp,
            "test_case_definition":self.check_template_tcd,
            "test_case":self.check_template_tc,
            "test_content":self.check_template_tcc
        }
        future_to_node = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            for nodo in levelorder_iter(nodo_raiz):
                description = ''
                openai_response={}
                if nodo.get_attr("report") is None or nodo.get_attr("report") == '':
                    nodo.set_attrs({"report": "ERROR - No description"})
                else:
                    description = nodo.get_attr("report")
                    print(f'Running OPEN AI FOR {nodo.get_attr("subject")}')
                    future = executor.submit(template_function[nodo.get_attr("subject")],templates, description, True, True)
                    future_to_node[future] = nodo
                    time.sleep(0.01)
    
            for future in as_completed(future_to_node):
                nodo = future_to_node[future]
                openai_response = future.result()
                # Extract the desired text and update the node attribute
                nodo.set_attrs({"report": self.get_text_between(openai_response, '```json', '```')})

        node_dict = tree_to_nested_dict(nodo_raiz, all_attrs=True)
        return node_dict
    """
    def get_text_between(self, content_list, start_text, end_text):
            """
            :param start_text: The text to start capturing content from.
            :param end_text: The text to stop capturing content at.
            :return: String containing the concatenated content between start_text and end_text.
            """
            if type(content_list) == str:
                content_list = [{'content': content_list}]
            result_content = []
            for item in content_list:
                if start_text in item['content']:
                    # Find the exact index of start_text
                    start_index = item['content'].find(start_text)
                    # Only proceed if end_text is found after start_text
                    end_index = item['content'].find(
                        end_text, start_index + len(start_text))
                    if end_index != -1:
                        # Extract content from after start_text to end_text
                        content = item['content'][start_index +
                                                len(start_text):end_index]
                        # Append the trimmed content to the result list
                        result_content.append(content)
                    else:
                        # If end_text is not found, capture all remaining text.
                        content = item['content'][start_index +
                                                len(start_text):]
                        result_content.append(content)
            return " ".join(result_content).strip()
        
    def parse_json_from_str(self, response) -> dict:
        try:
            return json.loads(self.get_text_between(response, '```json', '```'))
        except Exception as e:
            print(f'[ERROR] {e}: {response}')
            # return result_content
# if __name__ == '__main__':
#     from datetime import datetime
#     wiki = WikiConnector()
#     # prompt to be sent to the OpenAI model
#     # Select one from several examples
#     start = datetime.now()
#     template = wiki.get_tp_template()
#     system_msg = "You are a system validation engineer and need to review your test plan is well documented.\n"
#     system_msg += f"This is your Test Plan template {template['tp']}\n"
#     system_msg += f"This is your Test Case Description template {template['tcd']}\n"
#     system_msg += f"This is your Test Case template {template['tc']}\n"
#     system_msg += f"This is your Test Content template {template['content']}\n"
#     prompt = "Please explain me each part of the templates"

#     # print(
#     #     f"\nRunning prompt:\n   system: {system_msg}\n    user: {prompt}\n\n")

#     # messages to be sent to the OpenAI model
#     messages = [
#         {"role": "system", "content": system_msg},
#         {"role": "user", "content": prompt}
#     ]

#     # create an instance of the OpenAIConnector class
#     print("Starting openAI connection")
#     connector = OpenAIConnector()

#     # run the prompt on the OpenAI model
#     # print("Running query:\n%s"%(messages,))
#     res = connector.run_prompt(messages)

#     with open('openia.log', 'w') as file:
#         # print(f"The response: {res['response']}")
#         file.write(res['response'])

#     print(f'Execution time: {datetime.now() - start}')