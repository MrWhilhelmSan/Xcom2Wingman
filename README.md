# XCOM 2 Tactical Wingman

A local intelligent assistant (AI Agent) and strategic console designed to help XCOM 2 commanders make optimal base-building decisions, combat tactics choices, and soldier builds based on official guides and real game files.

---

## Features

- 📅 **Campaign Dashboard**: Control the month, Avatar Project progress, available resources, weapon/armor tiers, and active research. The campaign state is automatically injected into the agent's context.
- 💬 **Tactical Advisor**: An immersive chat with Central Officer Bradford (powered by Gemini) with direct access to local tactical databases.
- 🛠️ **MCP Integration**: Implements a local Model Context Protocol (MCP) server with tools to search relevant information semantically and via keywords in cleaned guides and game configurations.
- 📚 **Raw Search Utility**: A direct search utility interface to query fragments of strategy guides and configuration files from the game data (`DefaultGameData_COMBINADO.txt`).

---

## Requirements and Configuration

### 1. Set Up Your Gemini API Key
Obtain an API key from Google AI Studio and configure it as an environment variable:
```bash
# Windows (PowerShell)
$env:GEMINI_API_KEY="your_api_key_here"

# Windows (CMD)
set GEMINI_API_KEY="your_api_key_here"
```
*You can also enter the key directly in the sidebar text field of the Streamlit application.*

### 2. Install Dependencies
From the root folder of the project `tactical_wingman`, create a virtual environment and install the requirements:
```bash
# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

## Running the Application

### 1. Launch the Streamlit Web Interface
Run the following command to start the Streamlit application:
```bash
streamlit run app.py
```
A browser tab will automatically open (usually at `http://localhost:8507`).

### 2. Run and Test the MCP Server Locally
The MCP server is built using the FastMCP standard and can be run for development or integrated with editors like Cursor and Claude Desktop:
```bash
python mcp_server.py
```

To register the MCP server in **Claude Desktop**, add the following to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "xcom-wingman": {
      "command": "python",
      "args": ["C:/Users/carlo/Documents/XCOMGUIDE/tactical_wingman/mcp_server.py"]
    }
  }
}
```

---

## Tool Verification
You can verify that the XCOM 2 MCP server tools are responding and reading local guides correctly by running the test script:
```bash
python test_tools.py
```
This validates direct queries to the processed strategy guides and game configurations.
