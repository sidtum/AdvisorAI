# AdvisorAI

An intelligent academic advising system for Ohio State University's Computer Science & Engineering department that provides personalized course recommendations and program guidance.

## Overview

This AI-powered academic advisor helps CSE students at Ohio State University with:
- Course information and prerequisites
- Personalized course recommendations
- Degree requirement tracking
- Transcript analysis
- Interactive Q&A about the CSE curriculum

## Features

### Intelligent Course Assistance
- Detailed information about CSE courses, including:
  - Course descriptions
  - Prerequisites
  - Credit hours
  - Course levels (undergraduate/graduate)
  - Concurrent requirements

### Transcript Analysis
- Upload transcript functionality for personalized advice
- Automatic course history tracking
- Verification of completed prerequisites
- Tailored course recommendations based on academic history

### Interactive Chat Interface
- Real-time conversation with AI advisor
- Context-aware responses
- Consistent conversation memory
- Dark/light theme support

### Program Requirements Knowledge
- Complete understanding of BS CSE curriculum
- Major core requirements tracking
- Technical elective guidance
- Non-major course requirements
- Credit hour monitoring

# OSU CSE AI Academic Advisor

[Previous sections remain the same...]

## Technical Architecture

### Frontend
- React-based web application
- Real-time chat interface
- File upload support via react-dropzone
- Responsive design with theme switching
- Axios for API communication

### Backend
- Python-based server
- OpenAI GPT-4 integration for intelligent responses
- Course database management
- Transcript processing system
- Session management for conversation context

Reference:

### RAG System & Vector Database
- Implements Retrieval Augmented Generation for accurate course information
- ChromaDB vector store for efficient similarity search
- Embeddings-based course information retrieval
- Contextual response generation combining retrieved data with LLM capabilities

#### Vector Store Architecture
- Course information vectorized and stored in ChromaDB
- Includes:
  - Course descriptions
  - Prerequisites
  - Course numbers
  - Credit hours
  - Program requirements
- Real-time similarity search for relevant course data
- Efficient scaling for large course catalogs

#### RAG Pipeline
1. **Query Processing**
   - Student questions analyzed and vectorized
   - Semantic search through course embeddings
   - Relevant course information retrieved

2. **Context Enhancement**
   - Retrieved course data combined with query
   - Additional program requirements included when relevant
   - Prerequisites and course relationships maintained

3. **Response Generation**
   - GPT-4 generates responses using retrieved context
   - Ensures accuracy with official course information
   - Maintains conversational flow while providing precise data

### Benefits of RAG Implementation
- Higher accuracy compared to pure LLM responses
- Up-to-date course information
- Reduced hallucination risk
- Faster response times
- Scalable architecture

[Rest of the previous sections remain the same...]

## Setup and Installation

1. Clone the repository:
```
git clone https://github.com/your-username/osu-cse-advisor.git
```


2. Install frontend dependencies:
```
cd frontend
npm install
```


3. Install backend dependencies:
```
cd backend
pip install -r requirements.txt
```


4. Set up environment variables:
```
In Backend .env:
OPENAI_API_KEY=your_api_key
FLASK_APP=app.py
FLASK_ENV=development

In Frontend .env:
REACT_APP_API_URL=http://localhost:5000
```


5. Run the application:
```
cd backend
flask run
```

```
cd frontend
npm start
```

## Usage

1. Access the web interface at `http://localhost:3000`
2. Start a conversation with the AI advisor
3. Upload your transcript for personalized advice
4. Ask questions about courses, requirements, or program planning
