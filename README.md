# Agentic Policy Data Analytics Platform

Full-stack agentic analytics platform that answers policy research questions end-to-end using multi-source data integration, LLM-powered analysis, and transparent provenance tracking.

## 🚀 Quick Start with Docker

**Get the multi-agent system running in 4 steps - no Python installation required!**

### Step 1: Get API Keys

You need at least one (both recommended for automatic failover):
- **OpenAI**: https://platform.openai.com/api-keys → Get key starting with `sk-...`
- **Anthropic**: https://console.anthropic.com/ → Get key starting with `sk-ant-...`

### Step 2: Configure API Keys

**Windows:**
```cmd
cd infra
copy .env.example .env
notepad .env
```

**Linux/Mac:**
```bash
cd infra
cp .env.example .env
nano .env
```

Paste your API keys into the `.env` file:
```env
OPENAI_API_KEY=sk-your-actual-key-here
ANTHROPIC_API_KEY=sk-ant-your-actual-key-here
```
(You need at least one. Both recommended for failover.)

### Step 3: Start All Services

```cmd
docker-compose up -d
```

This starts: PostgreSQL, Redis, Backend API with agents, and Frontend UI.

### Step 4: Enjoy

Navigate to http://localhost:3000 


[ai-workflow-demo.webm](https://github.com/user-attachments/assets/455f96a7-125f-45d2-933b-e1e96625626f)

---

**🌐 Access Points:**
- **API Documentation (Interactive)**: http://localhost:8000/docs
- **Frontend UI**: http://localhost:3000

**📖 Documentation:**
- **[DOCKER_QUICKSTART.md](DOCKER_QUICKSTART.md)** - Complete Docker guide
- **[docs/AGENTS.md](docs/AGENTS.md)** - Multi-agent system architecture & detailed usage
