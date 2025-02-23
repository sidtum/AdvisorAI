import json
import re

def determine_course_level(course):
    """Determine if a course is undergraduate or graduate based on number and description"""
    course_num = course['number'].replace(' ', '')
    number = int(re.search(r'\d{4}', course_num).group())
    
    # By OSU's numbering system:
    # 1000-4999 are undergraduate
    # 5000+ are graduate
    is_graduate = number >= 5000
    
    # Additional checks in description for graduate keywords
    grad_keywords = ['graduate', 'masters', 'ph.d', 'doctoral']
    desc_lower = course['description'].lower()
    has_grad_keywords = any(keyword in desc_lower for keyword in grad_keywords)
    
    return "graduate" if is_graduate or has_grad_keywords else "undergraduate"

def process_courses():
    with open('cse_courses.json', 'r') as f:
        courses = json.load(f)
    
    # Add level field to each course
    for course in courses:
        course['level'] = determine_course_level(course)
    
    # Save processed courses
    with open('cse_courses_processed.json', 'w') as f:
        json.dump(courses, f, indent=4)

if __name__ == "__main__":
    process_courses() 