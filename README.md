# MCP Server Demo - GitHub Login Automation

This project demonstrates an **MCP (Model Context Protocol) server** integration with **Playwright** to automate GitHub login.

## 🚀 Features
- MCP server implementation for GitHub login automation
- Playwright-based browser automation
- Environment variable support for credentials
- Easily extensible for other GitHub workflows
![](https://github.com/Nikhil-Kandekar/mcp-server-demo/blob/master/ScreenRecording2025-09-13090923-ezgif.com-video-to-gif-converter.gif)
## 📂 Project Structure
```
mcp-server-demo/
│── server.py        # MCP server implementation
│── client.py        # Example MCP client to interact with server
│── requirements.txt # Dependencies
│── README.md        # Project documentation
```

## 🔧 Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Nikhil-Kandekar/mcp-server-demo.git
   cd mcp-server-demo
   ```

2. Create a virtual environment (recommended):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # On Linux/Mac
   .venv\Scripts\activate    # On Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## ⚙️ Environment Variables
Set your GitHub credentials as environment variables:

```bash
export GITHUB_USERNAME="your-username"
export GITHUB_PASSWORD="your-password"
```

For Windows PowerShell:
```powershell
setx GITHUB_USERNAME "your-username"
setx GITHUB_PASSWORD "your-password"
```

## ▶️ Running the MCP Server

Start the MCP server with:
```bash
python server.py
```

## ▶️ Running the Client

Run the example client to trigger GitHub login automation:
```bash
python client.py
```

## 🛠️ Development Notes
- If you run in a headless environment (e.g., server/CI), set **headless mode** in Playwright config.
- For headed mode on Linux servers without display, run with `xvfb-run`:
  ```bash
  xvfb-run -a python client.py
  ```

## 📌 Roadmap
- [ ] Extend tools for repo creation
- [ ] Add GitHub Actions workflow demo
- [ ] Dockerize the server

## 🤝 Contributing
Pull requests are welcome! For major changes, open an issue first to discuss what you’d like to change.

## 📜 License
This project is licensed under the MIT License.

---

**Author:** [Nikhil Kandekar](https://github.com/Nikhil-Kandekar)

