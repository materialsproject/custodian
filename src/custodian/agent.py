from custodian.custodian import ErrorHandler

class AgentHandler(ErrorHandler):
    def __init__(self, llm_interface, kb_path=None, skills_dir=None):
        self.llm_interface = llm_interface
        self.kb_path = kb_path
        self.skills_dir = skills_dir

    def check(self, directory="./"):
        self.llm_interface.chat(...)
        pass


    def correct(self, directory="./"):
        pass
