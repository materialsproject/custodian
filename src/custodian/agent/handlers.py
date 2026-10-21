
from custodian.custodian import ErrorHandler
    
class AgentHandler(ErrorHandler):
    def __init__(self, llm_interface, kb_path=None, skills_dir=None):
        self.errors: set[str] = set()
        self.llm_interface = llm_interface
        self.kb_path = kb_path
        self.skills_dir = skills_dir

    def check(self, directory="./"):
        """
        Use llm to identify error and generate actions
        """
        self.llm_interface.chat(...)
        pass


    def correct(self, directory="./"):
        pass
