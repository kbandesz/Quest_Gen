# App-wide limits
MODULE_TOKEN_LIMIT = 27_000

# Bloom content (UARK TIPS)
BLOOM_LEVELS = ["Remember","Understand","Apply","Analyze","Evaluate","Create"]

BLOOM_DEFS = {
    "Remember": "Retrieve, recognize, and recall relevant knowledge from long-term memory.",
    "Understand": "Construct meaning through interpreting, exemplifying, classifying, summarizing, inferring, comparing, and explaining.",
    "Apply": "Carry out or using a procedure for execution or implementation.",
    "Analyze": "Break material into parts and determining how the parts relate to one another and to an overall structure or purpose.",
    "Evaluate": "Make judgments based on criteria and standards through checking and critiquing.",
    "Create": "Put elements together to form a new whole; reorganize into a new pattern or structure through generating, planning, or producing.",
}

BLOOM_VERBS = {
    "Remember": "list, recite, outline, define, name, match, quote, recall, identify, label, recognize",
    "Understand": "describe, explain, paraphrase, restate, give original examples of, summarize, contrast, interpret, discuss",
    "Apply": "calculate, predict, apply, solve, illustrate, use, demonstrate, determine, model, perform, present",
    "Analyze": "classify, break down, categorize, analyze, diagram, illustrate, criticize, simplify, associate",
    "Evaluate": "choose, support, relate, determine, defend, judge, grade, compare, contrast, argue, justify, support, convince, select, evaluate",
    "Create": "design, formulate, build, invent, create, compose, generate, derive, modify, develop",
}

# General LO writing advice
LO_WRITING_TIPS = """
**Tips for Writing Effective Learning Objectives**

- Make sure there is **one measurable verb** in each objective; avoid vague verbs like *know*, *understand*, *learn*, *appreciate*.
- Keep objectives **clear and concise**.
- Ensure objectives are **aligned with course content**.
- Use the **Bloom's Taxonomy** framework to identify the cognitive skills learners need to demonstrate.
"""
# Assets
BLOOM_PYRAMID_IMAGE = "assets/Blooms_Taxonomy_pyramid.jpg"

# MOCK MODE: Use mock data and avoid real API calls (for local testing)
import io
import unittest.mock as mock
from datetime import datetime

# 1. Create a MagicMock object
mock_uploaded_file = mock.MagicMock()

# 2. Add content to a BytesIO object (as Streamlit does)
with open('assets/mock_module.txt', 'r', encoding='utf-8') as f:
    mock_content = f.read()
file_data = io.BytesIO(mock_content.encode('utf-8'))

# 3. Configure the mock with the required attributes and methods
mock_uploaded_file.configure_mock(
    # Set the file attributes
    name="mock_module.txt",
    size=len(mock_content.encode('utf-8')),
    last_modified=datetime.now(),
    
    # Set the behavior of the file methods
    read=mock.MagicMock(return_value=file_data.read()),
    seek=mock.MagicMock() # Many file functions call `seek(0)`
)
