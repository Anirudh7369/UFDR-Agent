# UFDR-Agent

A sophisticated AI-powered digital forensic analysis tool that leverages OpenAI Agents SDK with LiteLLM integration to analyze Universal Forensic Data Extraction (UFDR) reports. The system provides real-time forensic analysis capabilities through a FastAPI backend and web interface.

## 🎯 Overview

UFDR-Agent is designed to assist digital forensic investigators by analyzing chunks of forensic data from mobile devices, computers, and other digital sources. The agent acts as an elite-level AI Digital Forensic Investigator, capable of identifying critical connections, uncovering patterns, and highlighting details that human analysts might overlook due to time constraints or data volume.

### Key Features

- **AI-Powered Forensic Analysis**: Uses advanced AI models (Gemini) for deep forensic data analysis
- **Real-time Processing**: FastAPI-based REST API for immediate query processing
- **Multi-Source Data Support**: Handles call logs, SMS/MMS, emails, browser history, location data, file systems, and application data
- **Intelligent Cross-Referencing**: Correlates data across different sources to build comprehensive narratives
- **Structured Reporting**: Provides detailed forensic reports with timelines, connections, and investigative leads

## 🏗️ Architecture

```
UFDR-Agent/
├── realtime/                    # Main application directory
│   ├── main.py                 # FastAPI application entry point
│   ├── api/                    # API routes and endpoints
│   │   └── analytics/          # Analytics API endpoints
│   │       ├── routes.py       # Main analytics route handlers
│   │       └── __init__.py
│   ├── schemas/                # Pydantic models for API
│   │   └── opbects.py         # Request/Response schemas
│   ├── utils/                  # Utility modules
│   │   ├── ai/                # AI agent implementation
│   │   │   └── agent.py       # ForensicAgent class with LiteLLM
│   │   ├── prompts/           # AI agent prompts and instructions
│   │   │   └── Forensic_agent.py  # Detailed forensic analysis prompt
│   │   ├── time.py            # Time validation utilities
│   │   └── chat_session.py    # Session management
│   └── tools/                  # Additional tools and utilities
├── requirements.txt            # Python dependencies
└── README.md                  # This file
```

## 🚀 Setup

### Prerequisites

- Python 3.8 or higher
- Virtual environment (recommended)
- Gemini API key (Google AI)

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd UFDR-Agent
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv myenv
   source myenv/bin/activate  # On Windows: myenv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**:
   Create a `.env` file in the root directory:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   GEMINI_MODEL=gemini/gemini-1.5-flash
   ```

## 🎮 Usage

### Starting the Server

1. **Navigate to the realtime directory**:
   ```bash
   cd realtime
   ```

2. **Start the FastAPI server**:
   ```bash
   python main.py
   ```

3. **Access the API**:
   - Server will run on `http://localhost:8000`
   - API documentation available at `http://localhost:8000/docs`

### API Endpoints

#### POST `/api/analytics`

Processes forensic queries and returns detailed analysis.

**Request Body**:
```json
{
  "query": "What communications occurred before the suspicious file deletion?",
  "current_timestamp": "2025-10-10T18:45:01Z",
  "session_id": "session_123",
  "email_id": "investigator@example.com"
}
```

**Response**:
```json
{
  "message": "Detailed forensic analysis response...",
  "status": "success",
  "response": {
    "query": "What communications occurred before the suspicious file deletion?"
  },
  "session_id": "session_123",
  "status_code": 200
}
```

#### OPTIONS `/api/analytics`

Handles CORS preflight requests for web applications.

### Making Requests

**Using curl**:
```bash
curl -X POST "http://localhost:8000/api/analytics" \
     -H "Content-Type: application/json" \
     -d '{
       "query": "Analyze communication patterns around 2025-10-09 14:30",
       "session_id": "test_session"
     }'
```

**Using Python requests**:
```python
import requests

response = requests.post("http://localhost:8000/api/analytics", json={
    "query": "Show me all location data correlating with email activity",
    "session_id": "python_session"
})

print(response.json())
```

## 🤖 AI Agent Details

### ForensicAnalyst Agent

The core AI agent is configured with:

- **Model**: Gemini 1.5 Flash via LiteLLM
- **Role**: Elite-level AI Digital Forensic Investigator
- **Capabilities**:
  - Comprehensive data analysis across multiple forensic data types
  - Entity recognition and normalization
  - Chronological reconstruction with precise timestamps
  - Cross-referencing and correlation analysis
  - Pattern and anomaly detection
  - Relationship mapping and link analysis

### Supported Data Types

- **Communication Logs**: Call logs, SMS/MMS, instant messages
- **Email Data**: Full email analysis including metadata
- **Web Activity**: Browser history, search queries, cached content
- **Location Data**: GPS logs, cell tower data, Wi-Fi connections
- **File System Data**: File metadata, creation/modification times
- **Application Data**: Social media, banking, and app-specific data
- **Contacts**: Address book entries and relationships
- **Calendar Events**: Appointments and associated metadata

### Analysis Output Format

The agent provides structured reports including:

1. **Executive Summary**: Key findings overview
2. **Detailed Findings & Evidence**: Factual data points with sources
3. **Timeline of Relevant Events**: Chronological reconstruction
4. **Key Connections & Correlations**: Cross-referenced insights
5. **Potential Leads & Points of Interest**: Investigation recommendations

## 🔧 Configuration

### Environment Variables

- `GEMINI_API_KEY`: Your Google Gemini API key (required)
- `GEMINI_MODEL`: Gemini model to use (default: gemini/gemini-1.5-flash)

### CORS Configuration

The application is configured to accept requests from any origin during development. For production, update the CORS settings in `main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend-domain.com"],  # Specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 🧪 Development

### Project Structure

- **FastAPI Application**: Modern async web framework
- **Pydantic Models**: Type-safe request/response validation
- **LiteLLM Integration**: Unified interface for multiple AI providers
- **OpenAI Agents SDK**: Structured agent conversations and tool usage

### Adding New Features

1. **New API Endpoints**: Add routes in `realtime/api/`
2. **Agent Modifications**: Update prompts in `realtime/utils/prompts/`
3. **Data Models**: Extend schemas in `realtime/schemas/`
4. **Utilities**: Add helper functions in `realtime/utils/`

### Logging

The application includes comprehensive logging:
- Request/response logging for debugging
- Error tracking with full stack traces
- Agent interaction monitoring

## 🚨 Security Considerations

- **API Keys**: Never commit API keys to version control
- **Data Privacy**: Forensic data should be handled according to legal requirements
- **CORS**: Configure appropriate origins for production deployment
- **Input Validation**: All inputs are validated using Pydantic models

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and add tests
4. Commit your changes: `git commit -am 'Add new feature'`
5. Push to the branch: `git push origin feature-name`
6. Submit a pull request

## 📝 License

[Add license information here]

## 🆘 Support

For issues, questions, or contributions, please [create an issue](https://github.com/your-username/UFDR-Agent/issues) in the GitHub repository.