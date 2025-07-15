import streamlit as st

class MultiApp:
    """
    A class to combine multiple Streamlit applications into a single app,
    organized by sections.
    """

    def __init__(self):
        self.sections = {}  # Dictionary to hold all sections and their pages

    def add_app(self, section_name, page_title, page_func):
        """
        Register a new page under a specific section.

        Parameters:
        - section_name (str): Name of the top-level section (e.g., 'Reports')
        - page_title (str): Title of the page (e.g., 'Dashboard')
        - page_func (callable): The function to run that page (typically page_module.run)
        """
        if section_name not in self.sections:
            self.sections[section_name] = []
        self.sections[section_name].append({
            "title": page_title,
            "function": page_func
        })

    def run(self):
        """
        Render the sidebar with sections and pages,
        and call the run() function of the selected page.
        """
        # If no sections are registered, do nothing
        if not self.sections:
            st.write("No sections have been added to the application.")
            return

        st.sidebar.title("Navigation")

        # 1) List all section names in a selectbox
        section_names = list(self.sections.keys())
        selected_section = st.sidebar.selectbox("Choose a Section", section_names, index=section_names.index("Tools") if "Tools" in section_names else 0)

        # 2) From the chosen section, show all registered pages
        pages_in_section = self.sections[selected_section]
        page_titles = [page["title"] for page in pages_in_section]

        # Handle case where "Fuse CCB HSD Analysis" is not in page_titles
        default_page = "Fuse CCB HSD Analysis" if "Fuse CCB HSD Analysis" in page_titles else page_titles[0]
        selected_page = st.sidebar.radio("Choose a Page", page_titles, index=page_titles.index(default_page))

        # 3) Find and run the selected page function
        for page in pages_in_section:
            if page["title"] == selected_page:
                page["function"]()
                break
