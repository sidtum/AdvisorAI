import os
import json
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def init_database():
    # Initialize ChromaDB
    chroma_client = chromadb.PersistentClient(path="./chroma_db")
    
    # Initialize OpenAI embedding function
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=os.getenv('OPENAI_API_KEY'),
        model_name="text-embedding-ada-002"
    )

    # Load course data
    with open('cse_courses_processed.json') as f:
        courses = json.load(f)

    # Separate courses by level
    undergrad_courses = [c for c in courses if c['level'] == 'undergraduate']
    grad_courses = [c for c in courses if c['level'] == 'graduate']

    # Delete existing collections if they exist
    collection_names = ["undergrad_titles", "undergrad_courses", 
                       "grad_titles", "grad_courses"]
    for name in collection_names:
        try:
            chroma_client.delete_collection(name=name)
            print(f"Deleted existing collection: {name}")
        except:
            print(f"No existing collection found: {name}")

    # Create collections for each level
    collections = {
        'undergrad_titles': chroma_client.create_collection(
            name="undergrad_titles",
            embedding_function=openai_ef
        ),
        'undergrad_courses': chroma_client.create_collection(
            name="undergrad_courses",
            embedding_function=openai_ef
        ),
        'grad_titles': chroma_client.create_collection(
            name="grad_titles",
            embedding_function=openai_ef
        ),
        'grad_courses': chroma_client.create_collection(
            name="grad_courses",
            embedding_function=openai_ef
        )
    }

    # Function to process course batch
    def process_course_batch(courses, title_collection, full_collection):
        title_documents = []
        full_documents = []
        metadatas = []
        ids = []
        
        for i, course in enumerate(courses):
            course_num = course['number'].replace(' ', '')
            
            # Create title-focused document
            title_doc = f"""Course Number: {course_num} {course_num} {course_num}
Course: {course_num} - {course['title']}
Level: {course['level']}
Search Terms: {course_num} CSE {course_num[-4:]} {course['title']}"""
            
            # Create comprehensive document
            full_doc = f"""Course Number: {course_num} {course_num} {course_num}
Course Title: {course_num} - {course['title']}
Level: {course['level']}
Description: {course['description']}
Prerequisites: {course['prerequisites']}
Units: {course['units']}
Search Terms: {course_num} CSE {course_num[-4:]} {course['title']}"""
            
            title_documents.append(title_doc)
            full_documents.append(full_doc)
            metadatas.append({
                "number": course_num,
                "number_raw": course_num[-4:],
                "title": course['title'],
                "prerequisites": course['prerequisites'],
                "units": course['units'],
                "level": course['level']
            })
            ids.append(str(i))
        
        # Add documents to collections
        title_collection.add(
            documents=title_documents,
            metadatas=metadatas,
            ids=ids
        )
        full_collection.add(
            documents=full_documents,
            metadatas=metadatas,
            ids=ids
        )
        return len(title_documents)

    # Process undergraduate courses
    try:
        n_undergrad = process_course_batch(
            undergrad_courses,
            collections['undergrad_titles'],
            collections['undergrad_courses']
        )
        print(f"Added {n_undergrad} undergraduate courses")
        
        n_grad = process_course_batch(
            grad_courses,
            collections['grad_titles'],
            collections['grad_courses']
        )
        print(f"Added {n_grad} graduate courses")
        
    except Exception as e:
        print(f"Error adding documents to collections: {e}")

    # Add verification step
    try:
        # Verify a few known courses
        test_courses = ["CSE3901", "CSE3902", "CSE3241"]
        print("\nVerifying course entries:")
        for test_course in test_courses:
            result = collections['undergrad_courses'].get(
                where={"number": test_course}
            )
            if result['documents']:
                print(f"Found {test_course}: {result['documents'][0][:100]}...")
            else:
                print(f"WARNING: {test_course} not found in database!")
    except Exception as e:
        print(f"Error during verification: {e}")

if __name__ == "__main__":
    init_database() 