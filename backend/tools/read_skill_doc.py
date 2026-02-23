from langchain_core.tools import tool

from agent.skill_loader import get_skill_loader


@tool
def read_skill_doc(skill_name: str) -> str:
    """读取指定 Skill 的完整文档（SKILL.md），包含该 skill 提供的所有工具的详细说明和调用命令。
    当你在 system prompt 的 <available_skills> 中看到某个 skill，并判断它可能帮助完成用户任务时，
    必须先调用此工具获取完整文档，了解具体的脚本调用命令和参数，然后使用 shell_executor 执行相应命令。
    参数 skill_name 为 skill 的名称（如 'datetime-skill'）。"""
    loader = get_skill_loader()
    doc = loader.get_skill_doc(skill_name)
    if doc is None:
        available = [s.name for s in loader.loaded_skills]
        return f"错误：Skill '{skill_name}' 不存在。可用的 skills: {available}"
    return f"=== Skill '{skill_name}' 文档 ===\n\n{doc}"


@tool
def read_skill_reference(skill_name: str, file_path: str) -> str:
    """读取 Skill 的补充参考文档。某些 Skill 除了主文档外，还附带详细的参考文件
    （如 pitfalls.md、techniques.md 等），在主文档中会以 `see xxx.md` 的形式引用。
    当你需要更深入的信息时，使用此工具获取这些补充文档。
    参数 skill_name 为 skill 名称，file_path 为文件名（如 'pitfalls.md'）。"""
    loader = get_skill_loader()
    content = loader.get_skill_reference(skill_name, file_path)
    if content is None:
        skill = loader.catalog.get(skill_name)
        if skill is None:
            available = [s.name for s in loader.loaded_skills]
            return f"错误：Skill '{skill_name}' 不存在。可用的 skills: {available}"
        return f"错误：文件 '{file_path}' 在 Skill '{skill_name}' 中不存在。"
    return f"=== Skill '{skill_name}' / {file_path} ===\n\n{content}"
