import os
import json
import pandas as pd
import re
import numpy as np
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
import chromadb
from chromadb.utils import embedding_functions
import tiktoken
from dotenv import load_dotenv
from collections import deque
from datetime import datetime
import PyPDF2
from werkzeug.utils import secure_filename

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app) 

# Add these configurations after the CORS setup and before the routes
UPLOAD_FOLDER = './uploads'
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create uploads directory if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    """Check if the file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Initialize ChromaDB
chroma_client = chromadb.PersistentClient(path="./chroma_db")
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=os.getenv('OPENAI_API_KEY'),
    model_name="text-embedding-ada-002"
)

# Get both collections
try:
    title_collection_undergrad = chroma_client.get_collection(
        name="undergrad_titles",
        embedding_function=openai_ef
    )
    full_collection_undergrad = chroma_client.get_collection(
        name="undergrad_courses",
        embedding_function=openai_ef
    )
    title_collection_grad = chroma_client.get_collection(
        name="grad_titles",
        embedding_function=openai_ef
    )
    full_collection_grad = chroma_client.get_collection(
        name="grad_courses",
        embedding_function=openai_ef
    )
    print("Successfully connected to existing collections")
except Exception as e:
    print(f"Error connecting to collections: {e}")
    print("Please run init_db.py first to initialize the database")
    exit(1)

# Initialize conversation memory
conversation_memory = {}  # Dictionary to store conversations by session
MEMORY_LIMIT = 5  # Number of recent messages to remember
MEMORY_EXPIRY = 7200  # Session expiry in seconds (1 hour)

def get_session_memory(session_id):
    """Get or create conversation memory for a session"""
    now = datetime.now()
    
    # Clean up expired sessions
    expired = [sid for sid, data in conversation_memory.items() 
              if (now - data['last_access']).total_seconds() > MEMORY_EXPIRY]
    for sid in expired:
        del conversation_memory[sid]
    
    # Get or create session
    if session_id not in conversation_memory:
        conversation_memory[session_id] = {
            'messages': deque(maxlen=MEMORY_LIMIT),
            'last_access': now,
            'mentioned_courses': set(),
            'student_level': 'undergraduate',
            'transcript_courses': set(),
            'completed_courses': set()
        }
    else:
        conversation_memory[session_id]['last_access'] = now
    
    return conversation_memory[session_id]

def update_session_memory(session_id, user_message, ai_response, mentioned_courses):
    """Update session memory with new interaction"""
    memory = get_session_memory(session_id)
    memory['messages'].append({
        'user': user_message,
        'assistant': ai_response,
        'timestamp': datetime.now()
    })
    memory['mentioned_courses'].update(mentioned_courses)

def get_relevant_courses(query, session_id=None, n_results=3):
    """Retrieve relevant courses based on query and student level"""
    memory = get_session_memory(session_id) if session_id else None
    student_level = memory['student_level'] if memory else 'undergraduate'
    
    # Select appropriate collections based on student level
    title_collection = title_collection_grad if student_level == 'graduate' else title_collection_undergrad
    full_collection = full_collection_grad if student_level == 'graduate' else full_collection_undergrad
    
    query = query.upper()
    
    # Extract course numbers from current query and conversation history
    course_numbers = set()
    search_variations = []
    
    # Process current query
    patterns = [
        r'CSE\s*(\d{4})',
        r'(?<![\d])\d{4}(?![\d])'
    ]
    
    # First check current query
    for pattern in patterns:
        matches = re.findall(pattern, query)
        for match in matches:
            if isinstance(match, tuple):
                match = match[0]
            cse_num = f"CSE{match}"
            course_numbers.add(cse_num)
            search_variations.extend([
                f"Course Number: {cse_num}",
                f"Course: {cse_num}",
                cse_num,
                match
            ])
    
    # If no explicit course numbers in query, check memory for context
    if memory and not course_numbers:
        # Check if query contains references to "this course" or "it"
        reference_patterns = [
            r'\b(this|that|the|current|same) course\b',
            r'\bit\b',
            r'\bthis one\b'
        ]
        
        has_reference = any(re.search(pattern, query.lower()) for pattern in reference_patterns)
        if has_reference and memory['mentioned_courses']:
            # Add the most recently mentioned course
            last_course = list(memory['mentioned_courses'])[-1]
            course_numbers.add(last_course)
            search_variations.extend([
                f"Course Number: {last_course}",
                f"Course: {last_course}",
                last_course,
                last_course[-4:]
            ])
    
    results = []
    seen_courses = set()
    
    # First priority: Exact metadata match
    if course_numbers:
        for course_num in course_numbers:
            # Try exact metadata match
            exact_matches = full_collection.get(
                where={"number": course_num}
            )
            if exact_matches['documents']:
                for doc in exact_matches['documents']:
                    if doc not in seen_courses:
                        results.append(doc)
                        seen_courses.add(doc)
                continue
            
            # Try number_raw match if exact match fails
            raw_num = course_num[-4:]
            raw_matches = full_collection.get(
                where={"number_raw": raw_num}
            )
            if raw_matches['documents']:
                for doc in raw_matches['documents']:
                    if doc not in seen_courses:
                        results.append(doc)
                        seen_courses.add(doc)
    
    # If we found exact matches, return immediately
    if results:
        return {
            'documents': [results[:n_results]],
            'metadatas': [[]],
            'distances': [[]],
            'ids': [[]]
        }
    
    # Second priority: Enhanced semantic search with course number emphasis
    if course_numbers:
        # Create a weighted query that emphasizes the course number
        weighted_query = " ".join(search_variations + [query] * 2)
    else:
        weighted_query = query
    
    # Try title collection first
    title_results = title_collection.query(
        query_texts=[weighted_query],
        n_results=n_results
    )
    
    for i, doc_id in enumerate(title_results['ids'][0]):
        full_course = full_collection.get(
            ids=[doc_id]
        )
        if full_course['documents'][0] not in seen_courses and len(results) < n_results:
            results.append(full_course['documents'][0])
            seen_courses.add(full_course['documents'][0])
    
    # If we still need more results, try full collection
    if len(results) < n_results:
        full_results = full_collection.query(
            query_texts=[weighted_query],
            n_results=n_results
        )
        
        for doc in full_results['documents'][0]:
            if doc not in seen_courses and len(results) < n_results:
                results.append(doc)
                seen_courses.add(doc)
    
    return {
        'documents': [results],
        'metadatas': [[]],
        'distances': [[]],
        'ids': [[]]
    }

def create_prompt(query, relevant_courses, session_id=None):
    """Create a prompt combining user query, course information, and conversation history"""
    memory = get_session_memory(session_id) if session_id else None
    
    # Add transcript context if available
    transcript_context = ""
    if memory and memory['transcript_courses']:
        transcript_context = "\nStudent's completed courses from transcript:\n"
        transcript_context += ", ".join(sorted(memory['transcript_courses']))
        transcript_context += "\n"
    
    context = transcript_context + "\nRelevant courses:\n"
    
    # Extract course numbers and organize courses
    course_numbers = re.findall(r'CSE\s*\d{4}', query.upper())
    exact_matches = []
    related_courses = []
    mentioned_courses = set()
    
    for doc in relevant_courses['documents'][0]:
        # Extract course number from document
        course_match = re.search(r'CSE\d{4}', doc.split('\n')[0])
        if course_match:
            mentioned_courses.add(course_match.group())
            
        is_exact_match = any(course_num.replace(' ', '') in doc.split('\n')[0] 
                           for course_num in course_numbers)
        if is_exact_match:
            exact_matches.append(doc)
        else:
            related_courses.append(doc)
    
    # Add conversation history if available
    conversation_context = ""
    if memory and memory['messages']:
        conversation_context = "\nRecent conversation history:\n"
        for msg in memory['messages']:
            conversation_context += f"User: {msg['user']}\n"
            conversation_context += f"Assistant: {msg['assistant']}\n"
    
    # Combine all context
    for doc in exact_matches:
        context += f"\n[EXACT MATCH]\n{doc}\n"
    for doc in related_courses:
        context += f"\n[RELATED COURSE]\n{doc}\n"
    
    prompt = f"""You are an AI academic advisor at Ohio State University's Computer Science department. 
A student has asked: "{query}"

{conversation_context}
{context}

Please provide a clear, concise response that, using the provided information, directly addresses only the student's query.
If discussing prerequisites, check if the student has completed the required courses based on their transcript.
If recommending courses, consider the courses they've already taken.
If this is a follow-up question, maintain consistency with previous responses.

Response:"""
    
    return prompt, mentioned_courses

def query_openai(prompt):
    """Query OpenAI with the constructed prompt"""
    try:
        system_message = """You are an AI academic advisor for Ohio State University's Computer Science and Engineering department. 
You have expertise in the CSE curriculum and degree requirements for the BS CSE program.

Key degree requirements (BS CSE, Individualized Specialization):
- Total credit hours required: 126 minimum
- Major Core (42-45 credits):
  * Software sequence: CSE 2221, 2231 (8 credits)
  * Foundations sequence: CSE 2321, 2331 (6 credits)
  * Systems sequence: CSE 2421, 2431 (7 credits)
  * Required courses: CSE 3341, CSE 2501/PHILOS 2338, CSE 3901 or CSE 3902 or CSE 3903
  * Core electives: CSE 3231 or CSE 3241, CSE 3421 or CSE 3461, CSE 3521 or 3541
  * Capstone: CSE 5911-5916 (4 credits)

- Required Non-Major Courses:
  * Math: MATH 1151, 1172, 2568, 3345
  * Statistics: STAT 3470
  * Physics: PHYSICS 1250
  * Engineering: ECE 2020, 2060, ENGR 1181, 1182, 1100
  * Science/Math electives (8 credits)

- Technical Electives (17 credits):
  * CSE 3000+ level courses (≥9 credits)
  * Approved non-CSE 2000+ level courses (≤8 credits)
  * Restrictions on CSE 4251-4256 (max 2 hours)
  * Restrictions on CSE 4193, 4998, 4999 (max 6 hours combined)

When advising students:
1. Ensure prerequisites are met before recommending courses
2. Consider course sequencing and typical semester offerings
3. Help maintain steady progress toward degree completion
4. Consider both required courses and technical electives
5. Ensure recommendations align with degree requirements
6. Help with course planning and scheduling decisions"""

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error querying OpenAI: {e}")
        return "I apologize, but I'm having trouble generating a response right now. Please try again later."

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message')
    session_id = request.json.get('session_id')
    
    # Check if user is indicating their level
    level_patterns = {
        'graduate': r'\b(grad|graduate|master|masters|phd|doctoral)\b',
        'undergraduate': r'\b(undergrad|undergraduate)\b'
    }
    
    memory = get_session_memory(session_id)
    
    # Update student level if indicated in message
    for level, pattern in level_patterns.items():
        if re.search(pattern, user_input.lower()):
            memory['student_level'] = level
            response = f"I'll focus on {level} level courses for you. How can I help?"
            update_session_memory(session_id, user_input, response, set())
            return jsonify({"response": response})
    
    # Get relevant courses
    relevant_courses = get_relevant_courses(user_input, session_id)
    
    # Create prompt with context
    prompt, mentioned_courses = create_prompt(user_input, relevant_courses, session_id)
    
    # Get response from OpenAI
    response = query_openai(prompt)
    
    # Ensure newlines are preserved (not strictly necessary but good practice)
    response = response.replace('\n', '\n')
    
    # Update conversation memory
    update_session_memory(session_id, user_input, response, mentioned_courses)
    
    return jsonify({"response": response})

def extract_courses_from_pdf(file_path):
   """Extract text from PDF and identify course information"""
   try:
       pdf_reader = PyPDF2.PdfReader(file_path)
      
       # Check if PDF is encrypted
       if pdf_reader.is_encrypted:
           print("Error: This PDF is encrypted. Please provide an unencrypted PDF file.")
          
       text = ""
       for page in pdf_reader.pages:
           text += page.extract_text()


       # Check if text was extracted
       if not text.strip():
           print("Error: No text could be extracted from the PDF. Please ensure the PDF contains readable text.")
      


       # Create a prompt for OpenAI to extract course information
       prompt = f"""Please analyze this transcript text and extract all CSE (Computer Science) courses.
       Format the response as a list of course numbers only (e.g., CSE 1223, CSE 2221, etc.).
       Transcript text: {text}"""


       response = client.chat.completions.create(
           model="gpt-4",
           messages=[
               {"role": "system", "content": "You are a transcript analysis assistant. Extract only CSE course numbers from the transcript."},
               {"role": "user", "content": prompt}
           ]
       )
      
       return response.choices[0].message.content
   except Exception as e:
       print(f"Error processing PDF: {str(e)}")
       if "PyCryptodome" in str(e):
           return "Error: The PDF file appears to be encrypted. Please provide an unencrypted PDF file."
       return f"Error processing PDF: {str(e)}"


@app.route('/upload-transcript', methods=['POST'])
def upload_transcript():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    session_id = request.form.get('session_id')  # Change from request.json to request.form
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file and allowed_file(file.filename):
        file_path = None
        try:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # Extract courses from PDF
            courses = extract_courses_from_pdf(file_path)
            
            # Check if there was an error during extraction
            if isinstance(courses, str) and courses.startswith("Error:"):  # Add type check
                return jsonify({"error": courses}), 400
            
            # Get course information and update session memory
            course_info = []
            course_numbers = re.findall(r'CSE\s+\d{4}', courses)
            
            if not course_numbers:
                return jsonify({"error": "No CSE courses found in the transcript"}), 400
            
            # Update session memory with transcript courses
            if session_id:
                memory = get_session_memory(session_id)
                memory['transcript_courses'].update(course_numbers)
                memory['completed_courses'].update(course_numbers)
            
            for course_num in course_numbers:
                relevant_courses = get_relevant_courses(course_num, n_results=1)
                if relevant_courses['documents'][0]:
                    course_info.append(relevant_courses['documents'][0][0])
            
            response_text = f"""Based on your transcript, I can see you've taken the following courses:

{', '.join(course_num.strip() for course_num in course_numbers)}

I'll remember these courses for our conversation. Would you like specific information about any of these courses 
or recommendations for future courses based on your academic history?"""
            
            # Store this interaction in conversation memory
            if session_id:
                update_session_memory(
                    session_id,
                    "Uploaded transcript",
                    response_text,
                    set(course_numbers)
                )
            
            return jsonify({
                "response": response_text,
                "courses": course_info
            })
            
        except Exception as e:
            error_msg = str(e)
            print(f"Error in upload_transcript: {error_msg}")
            return jsonify({"error": f"Error processing file: {error_msg}"}), 500
        finally:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
    
    return jsonify({"error": "Invalid file type"}), 400




if __name__ == '__main__':
    app.run(debug=True)