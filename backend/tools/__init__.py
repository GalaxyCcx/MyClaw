from tools.read_file import read_file
from tools.write_file import write_file
from tools.web_fetch import web_fetch
from tools.web_search import web_search
from tools.python_executor import python_executor
from tools.shell_executor import shell_executor
from tools.read_skill_doc import read_skill_doc, read_skill_reference

BUILTIN_TOOLS = [
    read_file,
    write_file,
    web_fetch,
    web_search,
    python_executor,
    shell_executor,
    read_skill_doc,
    read_skill_reference,
]
