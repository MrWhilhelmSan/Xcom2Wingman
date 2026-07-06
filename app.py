import os
import re
import streamlit as st
import pandas as pd
from google import genai
from google.genai import types

# Import local MCP tools to use directly as Gemini tools
from mcp_server import search_strategy_guide, search_game_config, get_difficulty_mechanics
from typing import Optional

def override_context_from_query(query: str, context: dict) -> dict:
    """Parses user query to override sidebar values based on hierarchy (Chat > Menus)"""
    q = query.lower()
    
    word_to_num = {
        "zero": 0, "none": 0, "one": 1, "two": 2, "three": 3, "four": 4,
        "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
    }
    
    def extract_val(keywords: list) -> Optional[int]:
        for kw in keywords:
            # Pattern 1: kw is X
            p1 = rf'\b{kw}\b\s*(?:is|are|=)?\s*(\d+|\b(?:zero|none|one|two|three|four|five|six|seven|eight|nine|ten)\b)'
            m1 = re.search(p1, q)
            if m1:
                val_str = m1.group(1)
                if val_str.isdigit():
                    return int(val_str)
                return word_to_num.get(val_str, 0)
                
            # Pattern 2: X kw
            p2 = rf'(\d+|\b(?:zero|none|one|two|three|four|five|six|seven|eight|nine|ten)\b)\s*\b{kw}\b'
            m2 = re.search(p2, q)
            if m2:
                val_str = m2.group(1)
                if val_str.isdigit():
                    return int(val_str)
                return word_to_num.get(val_str, 0)
        return None

    # Supplies
    supplies_val = extract_val(["supplies", "supply", "suministros", "suministro"])
    if supplies_val is not None:
        context["Suministros"] = supplies_val

    # Intel
    intel_val = extract_val(["intel"])
    if intel_val is not None:
        context["Intel"] = intel_val

    # Alloys
    alloys_val = extract_val(["alloys", "alloy", "aleaciones", "aleacion"])
    if alloys_val is not None:
        context["Aleaciones"] = alloys_val

    # Elerium
    elerium_val = extract_val(["elerium", "elerio", "illyrium", "elerio"])
    if elerium_val is not None:
        context["Elerio"] = elerium_val

    # Engineers
    engineers_val = extract_val(["engineers", "engineer", "engineering", "ingenieros", "ingeniero"])
    if engineers_val is not None:
        context["Ingenieros"] = engineers_val

    # Scientists
    scientists_val = extract_val(["scientists", "scientist", "cientificos", "cientifico"])
    if scientists_val is not None:
        context["Cientificos"] = scientists_val

    # Power
    power_match = re.search(r'(\d+|\b(?:zero|none|one|two|three|four|five|six|seven|eight|nine|ten)\b)\s*(?:/|of)\s*(\d+|\b(?:zero|none|one|two|three|four|five|six|seven|eight|nine|ten)\b)\s*(?:of\s*)?power', q)
    if not power_match:
        power_match = re.search(r'power\s*(?:is|are|=)?\s*(\d+|\b(?:zero|none|one|two|three|four|five|six|seven|eight|nine|ten)\b)\s*(?:/|of)\s*(\d+|\b(?:zero|none|one|two|three|four|five|six|seven|eight|nine|ten)\b)', q)
        
    if power_match:
        used_str = power_match.group(1)
        total_str = power_match.group(2)
        used = int(used_str) if used_str.isdigit() else word_to_num.get(used_str, 0)
        total = int(total_str) if total_str.isdigit() else word_to_num.get(total_str, 15)
        context["Energia"] = f"{used}/{total}"

    # Research
    research_match = re.search(r'(?:research|investigacion)\s*(?:on the way|is|actual|=)?\s*(?:that is)?\s*([a-zA-Z0-9\s]+?)(?:,|\.|\bfor\b|\bin\b|\bthree\b|\b\d+\b|$)', q)
    if research_match:
        cand = research_match.group(1).strip()
        cand_clean = re.sub(r'\b(?:on the way|is|are|actual|a|an|the|that|to)\b', '', cand).strip()
        if cand_clean and len(cand_clean) > 3:
            context["Investigacion_Actual"] = cand_clean.title()

    return context

# Set page config with XCOM icon (a radar/target)
st.set_page_config(
    page_title="XCOM 2 Tactical Wingman",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom XCOM CSS styling for premium look
st.markdown("""
<style>
    /* Dark console background */
    .stApp {
        background-color: #0b0f19;
        color: #e0e6ed;
        font-family: 'Courier New', Courier, monospace;
    }
    
    /* Neon glowing borders for widgets */
    div[data-testid="stSidebar"] {
        background-color: #0f172a;
        border-right: 2px solid #00f2ff;
    }
    
    /* Header styling with neon gradient and scanlines effect */
    .xcom-header {
        background: linear-gradient(90deg, #002b3d 0%, #005a78 50%, #002b3d 100%);
        border: 1px solid #00f2ff;
        border-radius: 5px;
        padding: 20px;
        text-align: center;
        margin-bottom: 25px;
        box-shadow: 0 0 15px rgba(0, 242, 255, 0.2);
    }
    
    .xcom-title {
        color: #00f2ff;
        font-weight: bold;
        text-transform: uppercase;
        letter-spacing: 3px;
        margin: 0;
        font-size: 2.2rem;
        text-shadow: 0 0 10px rgba(0, 242, 255, 0.6);
    }
    
    .xcom-subtitle {
        color: #ff9d00;
        font-size: 0.9rem;
        letter-spacing: 2px;
        margin-top: 5px;
    }
    
    /* Style Chat Containers */
    .chat-bubble {
        padding: 15px;
        border-radius: 5px;
        margin-bottom: 12px;
        border-left: 5px solid;
        background-color: #1e293b;
    }
    
    .chat-user {
        border-left-color: #ff9d00;
        border-right: 1px solid rgba(255, 157, 0, 0.2);
    }
    
    .chat-agent {
        border-left-color: #00f2ff;
        border-right: 1px solid rgba(0, 242, 255, 0.2);
        box-shadow: 0 0 8px rgba(0, 242, 255, 0.05);
    }

    .chat-name {
        font-weight: bold;
        font-size: 0.85rem;
        text-transform: uppercase;
        margin-bottom: 5px;
        letter-spacing: 1px;
    }
    
    .chat-name-user {
        color: #ff9d00;
    }
    
    .chat-name-agent {
        color: #00f2ff;
    }
</style>
""", unsafe_allow_html=True)

# Main Title Header
st.markdown("""
<div class="xcom-header">
    <div class="xcom-title">👽 XCOM 2 Tactical Wingman</div>
    <div class="xcom-subtitle">COMMANDER'S INTELLIGENCE & STRATEGY CONSOLE v1.0</div>
</div>
""", unsafe_allow_html=True)

# Sidebar - Campaign State & Config
st.sidebar.markdown("<h3 style='color:#00f2ff;text-align:center;'>🛸 CAMPAIGN STATUS</h3>", unsafe_allow_html=True)

# API Key configuration (Secure Load)
env_key = os.environ.get("GEMINI_API_KEY", os.environ.get("GeminiApiKey", ""))

if env_key:
    api_key = env_key
    st.sidebar.markdown(
        "<div style='padding:10px; border-radius:5px; background-color:rgba(0, 242, 255, 0.1); border:1px solid #00f2ff; color:#00f2ff; text-align:center; font-weight:bold; letter-spacing:1px; font-size:0.85rem; margin-bottom:15px;'>"
        "🟢 WORKING WITH GEMINI"
        "</div>", 
        unsafe_allow_html=True
    )
else:
    api_key = st.sidebar.text_input(
        "Google Gemini API Key",
        type="password",
        value="",
        help="Provide your Google Gemini API Key. If running locally, you can paste it here. In production (Hugging Face), configure it as a Secret to keep it hidden."
    )

st.sidebar.markdown("---")

# Difficulty Configuration
difficulty_label = st.sidebar.selectbox(
    "🏆 Campaign Difficulty",
    ["Rookie", "Veteran", "Commander", "Legend"],
    index=2, # Default to Commander
    help="Defines the selected difficulty. Affects research times, resource costs, and hidden aim assistance."
)

diff_map = {
    "Rookie": {"name": "Rookie", "val": 0},
    "Veteran": {"name": "Veteran", "val": 1},
    "Commander": {"name": "Commander", "val": 2},
    "Legend": {"name": "Legend", "val": 3}
}
selected_diff = diff_map[difficulty_label]

st.sidebar.markdown("---")

# Campaign controls
campaign_month_option = st.sidebar.selectbox(
    "📅 Campaign Month",
    [
        "January",
        "February",
        "March (Start)",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September (Late Game)",
        "October",
        "November",
        "December",
        "Custom Date..."
    ],
    index=2, # March (Start) as default
    help="Select the campaign month or choose 'Custom Date...' to type a specific date."
)

if campaign_month_option == "Custom Date...":
    campaign_month = st.sidebar.text_input(
        "✍️ Enter Custom Date",
        value="February 15th",
        help="Type any date or month format you want."
    )
else:
    campaign_month = campaign_month_option

avatar_project = st.sidebar.slider(
    "🔴 Avatar Project (Progress)",
    min_value=0,
    max_value=12,
    value=3,
    help="Number of filled blocks in the Avatar Project."
)

weapon_tier = st.sidebar.selectbox(
    "🔫 Weapon Tier",
    ["Conventional (Tier 1)", "Magnetic (Tier 2)", "Plasma (Tier 3)"]
)

armor_tier = st.sidebar.selectbox(
    "🛡️ Armor Tier",
    ["Kevlar (Tier 1)", "Plated (Tier 2)", "Powered (Tier 3)"]
)

st.sidebar.markdown("**Available Resources:**")
col1, col2 = st.sidebar.columns(2)
with col1:
    supplies = st.number_input("Supplies", min_value=0, value=150, step=10)
    alloys = st.number_input("Alloys", min_value=0, value=30, step=5)
    power_used = st.number_input("Power Used", min_value=0, value=9, step=1)
    engineers = st.number_input("Engineers 🛠️", min_value=0, value=2, step=1)
with col2:
    intel = st.number_input("Intel", min_value=0, value=60, step=10)
    elerium = st.number_input("Elerium", min_value=0, value=10, step=5)
    power_total = st.number_input("Power Total", min_value=0, value=15, step=1)
    scientists = st.number_input("Scientists 🔬", min_value=0, value=1, step=1)

active_research = st.sidebar.text_input(
    "🧪 Active Research",
    value="Resistance Communications",
    placeholder="E.g., Modular Weapons, Plated Armor..."
)

st.sidebar.markdown("---")

# Campaign Objectives
st.sidebar.markdown("**Campaign Objectives:**")
selected_objectives = st.sidebar.multiselect(
    "🎯 Current Objectives",
    [
        "Tutorial",
        "ADVENT Officer Autopsy",
        "Build Proving Ground",
        "Research/Build Skulljack",
        "Skulljack ADVENT Officer",
        "Contact Blacksite Region",
        "Investigate Blacksite (Blacksite Mission)",
        "Build Shadow Chamber",
        "Analyze Blacksite Vial",
        "Skulljack a Codex",
        "Analyze Codex Brain",
        "Analyze Encrypted Codex Data",
        "Investigate Forge (Forge Mission)",
        "Analyze ADVENT Stasis Suit",
        "Investigate Psi Gate (Psi Gate Mission)",
        "Install Psi Gate in Shadow Chamber",
        "Avatar Autopsy",
        "Assault ADVENT Network Tower",
        "Assault Alien Fortress (Waterworld)",
        "Build Resistance Ring [WOTC]",
        "Contact Factions (Reapers/Skirmishers/Templars) [WOTC]",
        "Rescue Mox / Captured Soldier [WOTC]",
        "Covert Action: Locate Chosen Stronghold [WOTC]",
        "Assault Chosen Stronghold [WOTC]",
        "Custom Objective..."
    ],
    default=["Investigate Blacksite (Blacksite Mission)"],
    help="Select the current campaign objectives."
)

custom_objective = ""
if "Custom Objective..." in selected_objectives:
    custom_objective = st.sidebar.text_input(
        "✍️ Enter Custom Objective",
        placeholder="E.g., Contact a new region, defeat the Assassin..."
    )

final_objectives = []
for obj in selected_objectives:
    if obj == "Custom Objective...":
        if custom_objective:
            final_objectives.append(custom_objective)
    else:
        final_objectives.append(obj)

objectives_str = ", ".join(final_objectives) if final_objectives else "None"

st.sidebar.markdown("---")

# Chosen Configurator
with st.sidebar.expander("👑 Active Chosen Configurator"):
    chosen_name = st.selectbox("Current Chosen", ["None", "Assassin", "Hunter", "Warlock"])
    if chosen_name != "None":
        chosen_strengths = st.multiselect(
            "Strengths",
            ["Shadowstep", "Kinetic Plating", "Blast Shield", "Grounded", "Mind Shield", "Planeswalker", "Regeneration"],
            help="Select the Chosen's strength traits."
        )
        chosen_weaknesses = st.multiselect(
            "Weaknesses",
            ["Adversary: Reapers", "Adversary: Skirmishers", "Adversary: Templars", "Shell-Shocked", "Brittle", "Bewildered"],
            help="Select the Chosen's weakness traits."
        )
    else:
        chosen_strengths = []
        chosen_weaknesses = []

# Build State context dictionary
state_context = {
    "Dificultad": selected_diff["name"],
    "Dificultad_Valor": selected_diff["val"],
    "Mes": campaign_month,
    "Proyecto Avatar": f"{avatar_project}/12",
    "Armas": weapon_tier,
    "Armadura": armor_tier,
    "Suministros": supplies,
    "Intel": intel,
    "Aleaciones": alloys,
    "Elerio": elerium,
    "Energia": f"{power_used}/{power_total}",
    "Ingenieros": engineers,
    "Cientificos": scientists,
    "Investigacion_Actual": active_research,
    "Objetivos_Actuales": objectives_str,
    "Elegido_Activo": chosen_name,
    "Elegido_Fortalezas": ", ".join(chosen_strengths) if chosen_strengths else "None",
    "Elegido_Debilidades": ", ".join(chosen_weaknesses) if chosen_weaknesses else "None"
}

# Tabs for different functions
tab1, tab2 = st.tabs(["💬 TACTICAL ADVISOR CHAT", "📚 RAW DATABASE SEARCH"])

# Chat Interface
with tab1:
    # Define dynamic initial greeting message
    def get_initial_greeting():
        return (
            "Greetings, Commander. The Hologlobe is operational and I have loaded all strategic intelligence folders into our tactical query engine. Where do we need to focus our efforts today?"
        )

    # Initialize chat history
    if "messages" not in st.session_state or len(st.session_state.messages) == 0:
        st.session_state.messages = [
            {"role": "assistant", "content": get_initial_greeting()}
        ]

    # Action buttons at the top of the chat tab
    col_chat_title, col_chat_actions = st.columns([2, 1])
    with col_chat_title:
        st.markdown("### 📞 Communications Channel with the Tactical Advisor")
    with col_chat_actions:
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("🧹 Clear Chat", use_container_width=True, help="Clear the current chat history."):
                st.session_state.messages = []
                st.rerun()
        with btn_col2:
            safe_date = re.sub(r'[^a-zA-Z0-9]', '_', state_context['Mes']).strip('_')
            filename = f"xcom2_tactical_report_{safe_date}.md"
            
            report_lines = [
                "# XCOM 2 TACTICAL INTELLIGENCE REPORT",
                f"**Date (Game):** {state_context['Mes']}",
                f"**Campaign Difficulty:** {state_context['Dificultad']}",
                "",
                "## CAMPAIGN STATUS SUMMARY",
                "| Parameter | Current Value |",
                "| :--- | :--- |",
                f"| **Difficulty** | {state_context['Dificultad']} (Val: {state_context['Dificultad_Valor']}) |",
                f"| **Month / Date** | {state_context['Mes']} |",
                f"| **Supplies** | {state_context['Suministros']} |",
                f"| **Intel** | {state_context['Intel']} |",
                f"| **Alloys** | {state_context['Aleaciones']} |",
                f"| **Elerium** | {state_context['Elerio']} |",
                f"| **Power** | {state_context['Energia']} |",
                f"| **Engineers** | {state_context['Ingenieros']} 🛠️ |",
                f"| **Scientists** | {state_context['Cientificos']} 🔬 |",
                f"| **Weapon Tier** | {state_context['Armas']} |",
                f"| **Armor Tier** | {state_context['Armadura']} |",
                f"| **Current Research** | {state_context['Investigacion_Actual']} |",
                f"| **Current Objectives** | {state_context['Objetivos_Actuales']} |",
                f"| **Active Chosen** | {state_context['Elegido_Activo']} |",
                f"| **Chosen Strengths** | {state_context['Elegido_Fortalezas']} |",
                f"| **Chosen Weaknesses** | {state_context['Elegido_Debilidades']} |",
                "",
                "## COMMUNICATIONS LOG WITH CENTRAL BRADFORD",
                ""
            ]
            for msg in st.session_state.messages:
                role = "Commander" if msg["role"] == "user" else "Central Bradford"
                report_lines.append(f"### [{role}]")
                report_lines.append(msg["content"])
                report_lines.append("")
                
            report_content = "\n".join(report_lines)
            st.download_button(
                label="💾 Save Report",
                data=report_content,
                file_name=filename,
                mime="text/markdown",
                use_container_width=True,
                help="Download the campaign status and chat log as a Markdown report."
            )
            
    st.write("Consult the Advisor (Central Officer Bradford) about base-building choices, research priorities, enemy counters, or soldier builds.")

    # Container to hold chat history so it remains scrollable
    chat_container = st.container(height=500)

    # Display chat history inside the container
    with chat_container:
        for msg in st.session_state.messages:
            role_class = "chat-user" if msg["role"] == "user" else "chat-agent"
            name_class = "chat-name-user" if msg["role"] == "user" else "chat-name-agent"
            role_name = "Commander" if msg["role"] == "user" else "Central Bradford"
            
            st.markdown(f"""
            <div class="chat-bubble {role_class}">
                <div class="chat-name {name_class}">{role_name}</div>
                <div>{msg["content"]}</div>
            </div>
            """, unsafe_allow_html=True)

    # User query input (outside the container, so it's pinned to the bottom of the column/tab)
    user_query = st.chat_input("Enter tactical query or status report...")

    if user_query:
        # Display user message in the container immediately
        with chat_container:
            st.markdown(f"""
            <div class="chat-bubble chat-user">
                <div class="chat-name chat-name-user">Commander</div>
                <div>{user_query}</div>
            </div>
            """, unsafe_allow_html=True)
        st.session_state.messages.append({"role": "user", "content": user_query})

        # Process with Gemini
        if not api_key:
            st.error("⚠️ Error: Please provide your Google Gemini API Key in the sidebar.")
        else:
            with st.spinner("Establishing uplink and querying intelligence archives..."):
                try:
                    # Initialize client
                    client = genai.Client(api_key=api_key)
                    
                    system_instruction = (
                        "You are Central Officer Bradford, the Commander's chief tactical advisor in XCOM 2. "
                        "Your tone should be professional, military, tactical, and determined, always addressing the user as 'Commander'. "
                        "You have access to critical local tools: 'search_strategy_guide' (to search the clean strategy guide database), "
                        "'search_game_config' (to look up values in DefaultGameData_COMBINADO.txt, which can be filtered by difficulty) "
                        "and 'get_difficulty_mechanics' (to look up hidden aim assist modifiers, monthly enemy spawn timelines, and Chosen traits). "
                        "When the Commander asks you about combat tactics, soldier build guides, research queues, scan times, or difficulty parameters, "
                        "you must use the tools to retrieve specific records from the official guides, the compendium, and config files. "
                        "Always tailor your advice to the Commander's current campaign difficulty. For example, if the Commander plays on Rookie, "
                        "the guide's suggestions (which were written for Legend difficulty) about long research times and high resource costs must be appropriately contextualized, "
                        "and you should explain the hidden aim assistance (Aim Assist) of their difficulty if they ask about accuracy or missed shots. "
                        "Additionally, when the Commander presents you with choices, opportunities, or tactical trade-offs (such as prioritizing scanning sites, resource gathering vs. recruiting, or choosing mission paths), "
                        "you must conclude your response with a structured tactical recommendation report. In this report, list the options (e.g., Option A, Option B) and assign "
                        "a success probability/confidence percentage to each option based on your tactical assessment (e.g., Option A: 85% success probability, Option B: 60% success probability). "
                        "Explain your reasoning for these percentages briefly so the Commander can understand your level of confidence. "
                        "\n\n"
                        "CRITICAL REQUIREMENT: At the very beginning of EVERY response, before any greeting or tactical advice, you MUST output a sentence introducing the table, such as: 'Commander, here is the current tactical status I am basing my recommendations on:' or 'Based on our current campaign parameters:'. Immediately after this sentence, output the markdown table summarizing the campaign parameters. The table must be structured as follows:\n"
                        "| Parameter | Current Value |\n"
                        "| :--- | :--- |\n"
                        "| **Difficulty** | [Difficulty name from state status] |\n"
                        "| **Month / Date** | [Month/Date from state status] |\n"
                        "| **Supplies** | [Supplies value] |\n"
                        "| **Intel** | [Intel value] |\n"
                        "| **Alloys** | [Alloys value] |\n"
                        "| **Elerium** | [Elerium value] |\n"
                        "| **Power** | [Power value] |\n"
                        "| **Engineers** | [Engineers value] |\n"
                        "| **Scientists** | [Scientists value] |\n"
                        "| **Weapon Tier** | [Weapon tier value] |\n"
                        "| **Armor Tier** | [Armor tier value] |\n"
                        "| **Current Objectives** | [Current objectives list] |\n"
                        "\n"
                        "Immediately below the table, you must print this exact disclaimer text:\n"
                        "*(Note: If any of these parameters are incorrect, please adjust them in the sidebar config so I can update my tactical assessment.)*\n\n"
                        "HIERARCHY RULE: The Commander's query takes absolute priority. If there is a discrepancy between the campaign state block values and what the Commander explicitly describes in their query (e.g., resource counts, active research, power, engineers), you MUST use the values from the Commander's query for both your tactical advice and the parameter summary table.\n\n"
                        "CONFIG CONTENTS TIP: The DefaultGameData_COMBINADO.txt configuration file contains strategic settings (such as music, sounds, and UI configurations) but does NOT contain specific research point costs, technology templates, or weapon item statistics. Do NOT repeatedly query the game configuration tool 'search_game_config' for values like 'ResearchPoints', 'MagneticWeapons', or specific research project costs, as they are not present in that file. If a config search returns no results, do not retry with similar queries; instead, refer to the strategy guides or difficulty compendium, or answer using your built-in XCOM 2 knowledge base.\n\n"
                        "Always respond in English and maintain military immersion."
                    )
                    
                    # Prepare dynamic context (Chat > Menus hierarchy)
                    local_context = override_context_from_query(user_query, state_context.copy())
                    
                    # Prepare prompt with campaign state prefix
                    state_str = (
                        f"[XCOM CAMPAIGN STATE STATUS:\n"
                        f"- Active Difficulty: {local_context['Dificultad']} (Internal value: {local_context['Dificultad_Valor']})\n"
                        f"- Current Month: {local_context['Mes']}\n"
                        f"- Avatar Project Progress: {local_context['Proyecto Avatar']}\n"
                        f"- Weapon Tier: {local_context['Armas']}\n"
                        f"- Armor Tier: {local_context['Armadura']}\n"
                        f"- Resources: Supplies={local_context['Suministros']}, Intel={local_context['Intel']}, "
                        f"Alloys={local_context['Aleaciones']}, Elerium={local_context['Elerio']}, Power={local_context['Energia']}, "
                        f"Engineers={local_context['Ingenieros']}, Scientists={local_context['Cientificos']}\n"
                        f"- Current Research: {local_context['Investigacion_Actual']}\n"
                        f"- Current Objectives: {local_context['Objetivos_Actuales']}\n"
                        f"- Active Chosen: {local_context['Elegido_Activo']}\n"
                        f"  * Strengths: {local_context['Elegido_Fortalezas']}\n"
                        f"  * Weaknesses: {local_context['Elegido_Debilidades']}]\n\n"
                        f"Commander's query: {user_query}"
                    )
                    
                    # Call Gemini using chat/agent session with function calling
                    chat = client.chats.create(
                        model='gemini-2.5-flash',
                        config=types.GenerateContentConfig(
                            tools=[search_strategy_guide, search_game_config, get_difficulty_mechanics],
                            system_instruction=system_instruction,
                            temperature=0.4
                        )
                    )
                    
                    response = chat.send_message(state_str)
                    
                    # Show response inside container
                    with chat_container:
                        st.markdown(f"""
                        <div class="chat-bubble chat-agent">
                            <div class="chat-name chat-name-agent">Central Bradford</div>
                            <div>{response.text}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Error connecting to AI: {str(e)}")

# Raw Database Search Tab
with tab2:
    st.markdown("### 🔍 Direct Intelligence & Game Data Search")
    st.write("Use this tab to query raw data repositories directly without passing through the agent.")
    
    search_type = st.radio("Database to query", ["Strategy Guides (XcomClear)", "Game Configuration (GameConfig)", "Difficulty Mechanics (Wiki Compendium)"])
    db_query = st.text_input("Enter search terms", placeholder="E.g., Ranger build, Sectopod, SoundGlobalUI...")
    
    if st.button("Run Direct Query"):
        if not db_query:
            st.warning("Please enter a search query.")
        else:
            with st.spinner("Searching local archives..."):
                if search_type == "Strategy Guides (XcomClear)":
                    res = search_strategy_guide(db_query)
                    st.markdown("#### Found Guide Excerpts:")
                    st.code(res, language="text")
                elif search_type == "Game Configuration (GameConfig)":
                    res = search_game_config(db_query, difficulty=selected_diff["val"])
                    st.markdown(f"#### Found Configuration Values (Difficulty={selected_diff['val']}):")
                    st.code(res, language="ini")
                elif search_type == "Difficulty Mechanics (Wiki Compendium)":
                    res = get_difficulty_mechanics(selected_diff["name"])
                    st.markdown(f"#### Mechanics & Intel for Difficulty {selected_diff['name']}:")
                    st.code(res, language="text")
