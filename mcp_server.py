import os
import glob
import re
import json
import logging
from typing import Optional
from mcp.server.fastmcp import FastMCP

# Initialize logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("XCOM2-Tactical-Wingman-MCP")

# Define the FastMCP server
mcp = FastMCP("XCOM 2 Tactical Wingman")

# Bounded directories for security (Sandbox Check)
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
GUIDE_DIR = os.path.join(PROJECT_DIR, "data", "XcomClear")
CONFIG_FILE = os.path.join(PROJECT_DIR, "data", "DefaultGameData_COMBINADO.txt")
COMPENDIUM_FILE = os.path.join(PROJECT_DIR, "difficulty_compendium.json")

# In-memory caches for fast, read-only queries
_GUIDE_DOCS = None
_CONFIG_LINES = None

def verify_sandbox_path(path: str, base_directory: str = PROJECT_DIR) -> bool:
    """Verifies that the target path resolves inside the base directory sandbox."""
    real_base = os.path.realpath(base_directory)
    real_target = os.path.realpath(path)
    return real_target.startswith(real_base)

def load_compendium() -> dict:
    """Loads the difficulty compendium database safely."""
    if not os.path.exists(COMPENDIUM_FILE) or not verify_sandbox_path(COMPENDIUM_FILE):
        logger.error(f"Compendium file path invalid or not found: {COMPENDIUM_FILE}")
        return {}
    try:
        with open(COMPENDIUM_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to read difficulty compendium: {str(e)}")
        return {}

def get_documents() -> list:
    """Lazy-loads and caches strategic guides from the cleaned directory."""
    global _GUIDE_DOCS
    if _GUIDE_DOCS is not None:
        return _GUIDE_DOCS
        
    documents = []
    
    # 1. Load Xcom2 Missions Wiki if present
    missions_path = os.path.join(PROJECT_DIR, "data", "Xcom2 Missions.txt")
    if os.path.exists(missions_path) and verify_sandbox_path(missions_path):
        try:
            with open(missions_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            paragraphs = content.split('\n\n')
            for i, para in enumerate(paragraphs):
                para_clean = para.strip()
                if len(para_clean) > 30:
                    documents.append({
                        "source": "Xcom2 Missions Wiki",
                        "text": para_clean,
                        "index": i
                     })
        except Exception as e:
            logger.error(f"Error loading missions file: {str(e)}")

    if not os.path.exists(GUIDE_DIR) or not verify_sandbox_path(GUIDE_DIR):
        logger.warning(f"Guide directory path invalid or not found: {GUIDE_DIR}")
        _GUIDE_DOCS = documents
        return _GUIDE_DOCS
        
    # 2. Find and load all Clean_*.txt files
    files = glob.glob(os.path.join(GUIDE_DIR, "Clean_*.txt"))
    for filepath in files:
        if not verify_sandbox_path(filepath):
            continue
        filename = os.path.basename(filepath)
        if "DefaultGameData" in filename or "COMBINADO" in filename:
            continue
            
        part_match = re.search(r"Clean_(.+)\.txt", filename)
        part_name = part_match.group(1) if part_match else filename
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            paragraphs = content.split('\n\n')
            for i, para in enumerate(paragraphs):
                para_clean = para.strip()
                if len(para_clean) > 30:
                    documents.append({
                         "source": part_name,
                         "text": para_clean,
                         "index": i
                    })
        except Exception as e:
            logger.error(f"Error reading guide file {filename}: {str(e)}")
            
    _GUIDE_DOCS = documents
    return _GUIDE_DOCS

def get_config_lines() -> list:
    """Lazy-loads and caches the main game config file to prevent high I/O overhead."""
    global _CONFIG_LINES
    if _CONFIG_LINES is not None:
        return _CONFIG_LINES
        
    if not os.path.exists(CONFIG_FILE) or not verify_sandbox_path(CONFIG_FILE):
        logger.error(f"Config file invalid or not found: {CONFIG_FILE}")
        _CONFIG_LINES = []
        return _CONFIG_LINES
        
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
            _CONFIG_LINES = f.readlines()
        logger.info(f"Successfully cached {len(_CONFIG_LINES)} lines from config file.")
    except Exception as e:
        logger.error(f"Failed to read config file: {str(e)}")
        _CONFIG_LINES = []
        
    return _CONFIG_LINES

@mcp.tool()
def search_strategy_guide(query: str) -> str:
    """
    Search the XCOM 2 strategy guides for tactical advice, research orders, build queues,
    soldier classes, enemy weaknesses, and mission strategies.
    
    Use this tool WHEN the user asks for combat tips, build suggestions, project timelines, 
    or gameplay strategies against specific aliens.
    
    Args:
        query: The search query containing keywords (e.g., 'Mec enemy', 'Specialist build').
        
    Returns:
        A list of up to 5 matching strategy guide excerpts sorted by relevance.
    """
    # Sanitize query to prevent search parsing issues
    query_clean = re.sub(r'[^\w\s\-\:]', '', query).strip()
    if not query_clean:
        return "ERROR: Please provide a query with alphanumeric characters."
        
    docs = get_documents()
    if not docs:
        return "ERROR: No strategy guide files found in the source directory."
        
    words = [w.lower() for w in re.findall(r'\w+', query_clean) if len(w) > 2]
    if not words:
        return "ERROR: Please provide specific keywords (longer than 2 characters)."
        
    scored = []
    for doc in docs:
        score = 0
        text_lower = doc["text"].lower()
        
        for word in words:
            if word in text_lower:
                score += 2
                score += text_lower.count(word) * 0.2
                
        if query_clean.lower() in text_lower:
            score += 10
            
        if score > 0:
            scored.append((score, doc))
            
    scored.sort(key=lambda x: x[0], reverse=True)
    
    results = []
    for score, doc in scored[:5]:
        results.append(
            f"--- SOURCE: {doc['source']} (Paragraph {doc['index']}) (Relevance: {score:.1f}) ---\n{doc['text']}"
        )
        
    if not results:
        return f"No tactical advice found in the guide for the query: '{query_clean}'."
        
    return "\n\n".join(results)

@mcp.tool()
def search_game_config(query: str, difficulty: Optional[int] = None) -> str:
    """
    Search the DefaultGameData_COMBINADO.txt file for internal XCOM 2 game rules, 
    values, or settings configurations.
    
    Use this tool WHEN the user asks for exact game statistics, numeric values, 
    balancing variables, or game engine configurations.
    
    Args:
        query: Config variable name or section to find (e.g., 'AkEvent', 'TacticalCombatMusicSets').
        difficulty: Optional difficulty level (0=Rookie, 1=Veteran, 2=Commander, 3=Legend) to filter difficulty-specific parameters.
        
    Returns:
        Up to 25 lines matching the config query, indicating line number and section.
    """
    query_clean = re.sub(r'[^\w\s\-\_\[\]]', '', query).strip()
    if not query_clean:
        return "ERROR: Please provide a valid config parameter name."
        
    lines = get_config_lines()
    if not lines:
        return "ERROR: Game configuration file is empty or could not be loaded."
        
    query_lower = query_clean.lower()
    matching_lines = []
    current_section = "[No Section]"
    
    for i, line in enumerate(lines):
        line_strip = line.strip()
        if line_strip.startswith('[') and line_strip.endswith(']'):
            current_section = line_strip
            
        if query_lower in line.lower():
            if difficulty is not None and "difficulty=" in line_strip.lower():
                diff_match = re.search(r'difficulty\s*=\s*(\d+)', line_strip, re.IGNORECASE)
                if diff_match:
                    line_diff = int(diff_match.group(1))
                    if line_diff != difficulty:
                        continue
            
            matching_lines.append((i + 1, current_section, line_strip))
            
    if not matching_lines:
        filter_str = f" with difficulty={difficulty}" if difficulty is not None else ""
        return f"No configuration lines found matching '{query_clean}'{filter_str}."
        
    output = []
    for line_num, section, content in matching_lines[:25]:
        output.append(f"Line {line_num} | Section: {section}\n  Value: {content}")
        
    return "\n".join(output)

@mcp.tool()
def get_difficulty_mechanics(difficulty_name: str) -> str:
    """
    Get detailed information about game mechanics, player aim assist, hidden modifiers,
    and enemy encounter tables for a specific difficulty level.
    
    Use this tool WHEN the user asks about hidden aim assist percentages, the calendar 
    timeline of monthly enemy appearances, or possible Chosen traits (strengths/weaknesses).
    
    Args:
        difficulty_name: The difficulty name ('Rookie', 'Veteran', 'Commander', 'Legend').
        
    Returns:
        Structured breakdown of aim assist modifiers, monthly timelines, and Chosen traits.
    """
    compendium = load_compendium()
    if not compendium:
        return "ERROR: Could not load the difficulty compendium database."
        
    diffs = compendium.get("aim_assist", {})
    matched_diff = None
    for name in diffs.keys():
        if name.lower() == difficulty_name.lower():
            matched_diff = name
            break
            
    if not matched_diff:
        return f"ERROR: Difficulty '{difficulty_name}' not found. Available options: {list(diffs.keys())}"
        
    aim = diffs[matched_diff]
    timeline = compendium.get("enemy_timeline", {})
    timeline_str = []
    for month, info in timeline.items():
        enemies = ", ".join(info.get("enemigos_comunes", []))
        timeline_str.append(
            f"- **{month}**:\n"
            f"  * Enemies: {enemies}\n"
            f"  * Tactical Priority: {info.get('prioridad_tactica', '')}\n"
            f"  * Key Event: {info.get('evento_clave', '')}"
        )
        
    chosen = compendium.get("chosen_traits", {})
    weaknesses = "\n".join([f"- **{w['nombre']}**: {w['descripcion']}" for w in chosen.get("debilidades", [])])
    strengths = "\n".join([f"- **{s['nombre']}**: {s['descripcion']}" for s in chosen.get("fortalezas", [])])
    
    res = (
        f"=== MECHANICS & INTEL FOR DIFFICULTY: {matched_diff.upper()} ===\n\n"
        f"--- AIM ASSIST ---\n"
        f"- Base Multiplier: {aim.get('base_multiplier')}\n"
        f"- Consecutive Miss Bonus: {aim.get('consecutive_miss_bonus')}\n"
        f"- Enemy Consecutive Hit Penalty: {aim.get('enemy_consecutive_hit_penalty')}\n"
        f"- Hidden Mechanics: {aim.get('hidden_mechanics')}\n\n"
        f"--- ENEMY SPAWN TIMELINE ---\n"
        f"{chr(10).join(timeline_str)}\n\n"
        f"--- CHOSEN TRAITS POOL ---\n"
        f"**Possible Weaknesses:**\n{weaknesses}\n\n"
        f"**Possible Strengths:**\n{strengths}"
    )
    return res

if __name__ == "__main__":
    mcp.run()
