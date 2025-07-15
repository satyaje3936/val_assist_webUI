from bs4 import BeautifulSoup
from bigtree import Node
import connectors.hsd_connector as HSD
import threading
import time

class HSDHandler:
    def __init__(self):
        self.hsd = HSD.HsdConnector()

    def get_hsd_description(self, hsd_id):
        # # print(hsd_id, type(hsd_id))
        hsd = self.hsd.get_hsd(hsd_id, ['description','from_subject','tenant'] )
        # # print(hsd)
        if self.validate_hsd(hsd) == 0:
            html_desc = hsd['description']
        if html_desc is None:
            return ''
        else:
            soup = BeautifulSoup(html_desc, "html.parser")
            return soup.text
    
    def validate_hsd(self,hsd):
        __supported_tenants = ["server", "validation_central"]
        __supported_tenants_subjects = ["test_plan", "test_case_definition", "test_case", "test_content", None]
        if(hsd['tenant'] not in __supported_tenants):
            raise Exception("Tenant not supported")
        if(hsd['from_subject'] not in __supported_tenants_subjects):
            raise Exception("Tenant Subject not supported")
        return 0

    def get_hsd_tree(self, hsd_id, node_parent, is_test_plan=False):
        time.sleep(0.001)
        data = self.hsd.get_hsd(hsd_id)
        self.validate_hsd(data)
        node_dict = {
            "name": data['title'],
            "id": data['id'],
            "owner": data['owner'],
            "report": BeautifulSoup(data['description'], "html.parser").text if data['description'] != None else '',
            "subject": data["subject"],
            "parent": node_parent,
            "status": data.get('status', ''),
            "priority": data.get('priority', ''),
            "title": data['title']  # Ensure title is included
        }
        root = Node.from_dict(node_dict)
        links = self.hsd.get_hsd_links(hsd_id)

        threads = []
        for hsd_link in links['responses']:
            # Ensure the hierarchy: TP > TPF > TCD > TC
            if hsd_link['relationship'] == 'parent-child':
                if hsd_link['subject'] == 'test_plan_feature' and hsd_link['parent_id'] == hsd_id:
                    # Link TPF under TP
                    thread = threading.Thread(
                        target=self.get_hsd_tree,
                        args=(hsd_link['id'], root, False)
                    )
                elif hsd_link['subject'] == 'test_case_definition' and hsd_link['parent_id'] == hsd_id:
                    # Link TCD under TPF
                    thread = threading.Thread(
                        target=self.get_hsd_tree,
                        args=(hsd_link['id'], root, False)
                    )
                elif hsd_link['subject'] == 'test_case' and hsd_link['parent_id'] == hsd_id:
                    # Link TC under TCD
                    thread = threading.Thread(
                        target=self.get_hsd_tree,
                        args=(hsd_link['id'], root, False)
                    )
                else:
                    continue
                threads.append(thread)
                thread.start()

        for thread in threads:
            thread.join()

        # Ensure the root node is returned only for the top-level call
        if node_parent is None:
            return root
        
    #Function that perform the query to HSD to request HSD links details
    def __get_hsd_info(self, hsd_id):
        fields = ["id","subject","tenant","title","owner","status","relationship"]
        ## print("Getting info...")
        rsp = self.hsd.get_hsd_links(hsd_id, fields)
        parent_name = self.hsd.get_hsd(hsd_id, ['title'] )['title']
        ## print("Ready!")
        return parent_name, rsp.get("responses")


    #In this function we take in consideration only pvim folders and test plans
    def __parse_info(self, llist, parent_name):
        opt_dict = [{'text': parent_name, 'children':[]}]
        for item in llist:
            relationship = item.get("relationship")
            # tenant = item.get('tenant')
            subject = item.get('subject')
            id_hsd = item.get('id')
            title = item.get('title')
            if relationship == 'child-parent':
                continue
            if subject != "folder" and subject != "test_plan":
                continue
            # is_test_plan = True if subject == 'test_plan' else False
            values = {'text': title, 'id': id_hsd, 'children':[]}
            opt_dict[0]['children'].append(values)
        return opt_dict
    
    def get_parent_node(self, hsd_id):
        parent_name, links = self.__get_hsd_info(hsd_id)
        parent_node = self.__parse_info(links, parent_name)
        parent_node[0]['id'] = hsd_id
        return parent_node
            

#Class to save the children and parent relationship
class Tree:
    def __init__(self):
        self.nodes = {}

    def add_node(self, parent, children):
        self.nodes[parent] = children

    def get_children(self, parent):
        return self.nodes.get(parent, [])

    def has_parent(self, child):
        return any(child in children for children in self.nodes.values())

    def get_parent(self, child):
        for parent, children in self.nodes.items():
            if child in children:
                return parent
        return None
    
    def print_all_descendants(self, parent, depth=0):
        children = self.get_children(parent)
        if not children:
            return
        else:
            for child in children:
                # # print("  " * depth + child)
                self.print_all_descendants(child, depth + 1)

#For CMD prompt to dinamically show the options and return the selected index
def _menu_prompt(options, msg=None, rtn_feature=False):
    # if msg is not None:
        # print(msg)
    # for index, option in enumerate(options, start=1):
        # print(f"\t{index}) {option.capitalize()}")
    while (True):
        try:
            user_input = input("\nSelection: ")
            chosen_index = (int(user_input) - 1)
            if (chosen_index+1) == len(options) and rtn_feature:
                # print("Returning\n")
                return -1
            elif 0 <= chosen_index < len(options):
                # print(f"Option {options[chosen_index]} selected\n")
                return chosen_index
            else:
                pass
                # print("Invalid input. Please choose a valid option.")
        except Exception as e:
            # print("Error in the options function...")
            # print(e)
            return None

#Function that perform the query to HSD to request HSD links details
def _get_hsd_info(hsd_id):
    fields = ["id","subject","tenant","title","owner","status","relationship"]
    ## print("Getting info...")
    hsd = HSDHandler()
    rsp = hsd.hsd.get_hsd_links(hsd_id, fields)
    ## print("Ready!")
    return rsp.get("responses")

#In this function we take in consideration only pvim folders and test plans
def _process_info(llist):
    opt_dict = {}
    ctt = 0
    for item in llist:
        relationship = item.get("relationship")
        tenant = item.get('tenant')
        subject = item.get('subject')
        id_hsd = item.get('id')
        title = item.get('title')
        if relationship == 'child-parent':
            continue
        if subject != "folder" and subject != "test_plan":
            continue
        is_test_plan = True if subject == 'test_plan' else False
        values = (id_hsd,title,tenant,subject,is_test_plan)
        opt_dict[ctt] = values
        ctt+=1
    return opt_dict

#Main function to iterate over the pvim folders
def run_main():
    import os
    os.system("cls")
    # print("Application intended for IP/SOC validators")
    tree = Tree()
    pvim_start = '1015583783'  #parent pvim folder
    hsd_2_search = pvim_start
    tp_found = False
    while not tp_found:
        extract_info = _get_hsd_info(hsd_2_search)
        options = _process_info(extract_info)
        llist = []
        id_num = []
        for opt in options.keys():
            rsp = options.get(opt)
            visual = rsp[1] + "\t(" + rsp[3] + ")"
            llist.append(visual)
            id_num.append(rsp[0])
        #Saving the hierarchy of the found HSD
        tree.add_node(hsd_2_search, id_num)
        #Return to previous folder is not available in the root folder
        if pvim_start != hsd_2_search:
            llist.append("Return to previous folder")
            rtn_feature = True
        else:
            rtn_feature = False
        #Create the cmd prompt menu for the folder selection
        sel_opt = _menu_prompt(llist, "Select an option:", rtn_feature)
        if sel_opt == -1:
            hsd_2_search = tree.get_parent(hsd_2_search)
            continue
        values = options.get(sel_opt)
        #If the selected HSD is a test plan we can finish the function
        hsd_2_search = values[0]
        if values[4]:
            tp_found = True
    # print("Your selected test plan is:",hsd_2_search)
    return hsd_2_search
    
if __name__ == "__main__":
    # print("Running function")
    run_main()