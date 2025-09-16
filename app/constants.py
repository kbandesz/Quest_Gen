import io
import random
import json
import time
import unittest.mock as mock
from datetime import datetime
from typing import Dict, Any

# App-wide limits
MODULE_TOKEN_LIMIT = 27_000

# Module structure guidance
COURSE_STRUCTURE_GUIDANCE = """
Courses have the following **structure**:
1. Module
    1. Section
        1. Unit

A course may have multiple **modules**.
- **Module Duration:** 2-3 hours of learning
  - includes ALL learning content elements (text, videos, assessments, activities, etc.)
  - rough estimate: 9,000 words (15 pages) of text per hour
- **Sections:** 4-5 per module, directly linked to the module's learning objectives 
- **Units:** Multiple per section
- **Balance of modalities:** Mix text, graphics, video, activities, etc.
"""

# Bloom levels and definitions
BLOOM_DEF = """
**Bloom's Taxonomy** is an important educational framework that categorizes different levels of cognitive
processes involved in learning. When writing learning objectives, consider the complexity of the cognitive
skills you want the learners to acquire or demonstrate (and that they can feasibly acquire or
demonstrate).
"""

BLOOM_LEVEL_DEFS = {
    "Remember": "Recall facts and basic concepts",
    "Understand": "Explain ideas or concepts.",
    "Apply": "Use information in new situations.",
    "Analyze": "Draw connections among ideas.",
    "Evaluate": "Justify a stand or decision.",
    "Create": "Produce new or original work.",
}

BLOOM_VERBS = {
    "Remember": "define, describe, identify, label, list, locate, match, memorize, recall, repeat, select, state",
    "Understand": "classify, compare, contrast, describe, discuss, distinguish, explain, illustrate, interpret, order, report, summarize",
    "Apply": "calculate, compute, construct, develop, demonstrate, implement, interpret, manipulate, modify, predict, produce, solve",
    "Analyze": "categorize, compare, contrast, deduce, differentiate, estimate, examine, infer, prioritize, organize, question, test",
    "Evaluate": "argue, convince, critique, defend, justify, measure, persuade, predict, rate, select, support, weigh",
    "Create": "assemble, compose, construct, create, design, develop, formulate, integrate, plan, propose, schematize, simulate"
}

BLOOM_PYRAMID_IMAGE = "assets/Blooms_Taxonomy_pyramid.jpg"

# LO writing guidance
LO_DEF = """
**Learning objectives** are statements that answer the question: What will learners be able to do upon
completion of a course or training?

Learning objectives have two main parts:
1. an **action verb**: the desired learner behavior
2. a **content/skill area**: a description of the target content or skill
"""

LO_WRITING_TIPS = {
    "smart_criteria": """
**SMART Learning Objectives:**
- **S**pecific - Clear and unambiguous
- **M**easurable - Observable and assessable
- **A**chievable - Realistic for the course duration
- **R**elevant - Aligned with course goals
- **T**ime-bound - Achievable within module timeframe
    """,
    "avoid_verbs": ["Appreciate", "Aware of", "Comprehend", "Familiar with", "Know", "Learn", "Realize", "Understand"],
}

# Questions writing guidance
QUESTION_TIPS = {
        "stem_writing": "Keep stems clear and complete. Avoid partial sentences.",
        "distractor_writing": "Make distractors plausible but clearly incorrect.",
        "feedback_writing": "Explain why each option is correct or incorrect."
}

############################################
# MOCK MODE - No API calls (for offline testing and demos)
############################################
# Create mock file (for source material and module upload)
def create_mock_file(mock_file_path: str):
    """Load the mock text file used in MOCK_MODE."""

    # 1. Create a MagicMock object
    mock_uploaded_file = mock.MagicMock()

    # 2. Add content to a BytesIO object (as Streamlit does)
    with open(mock_file_path, 'r', encoding='utf-8') as f:
        mock_content = f.read()
    file_data = io.BytesIO(mock_content.encode('utf-8'))

    # 3. Configure the mock with the required attributes and methods
    mock_uploaded_file.configure_mock(
        # Set the file attributes
        name="mock_uploaded_file.txt",
        size=len(mock_content.encode('utf-8')),
        last_modified=datetime(2025, 9, 4), # datetime.now()
        
        # Set the behavior of the file methods
        read=mock.MagicMock(return_value=file_data.read()),
        seek=mock.MagicMock() # Many file functions call `seek(0)`
    )
    return mock_uploaded_file

# Mock alignment scenarios
def generate_mock_alignment_result(lo_text: str, intended_level: str) -> Dict[str, Any]:
    """Pick one mock alignment outcome at random."""

    MOCK_ALIGNMENT_SCENARIOS = [
        # 1) Consistent — no rewrite needed
        lambda lo_text, intended_level: {
            "label": "consistent",
            "reasons": [f"Primary verb and cognitive demand match '{intended_level}'.", "LO is measurable and specific."],
            "suggested_lo": None,
        },
        # 2) Ambiguous — suggest sharper rewrite
        lambda lo_text, intended_level: {
            "label": "ambiguous",
            "reasons": ["LO mixes multiple actions or vague phrasing (e.g., 'understand', 'know')."],
            "suggested_lo": f"Revise to a single measurable verb at {intended_level}: Replace vague phrasing in \"{lo_text}\" with a concrete outcome (e.g., 'analyze X by comparing Y and Z using criteria A').",
        },
        # 3) Inconsistent — suggest rewrite aligned to intended level
        lambda lo_text, intended_level: {
            "label": "inconsistent",
            "reasons": [f"Stated verb implies a different Bloom level than '{intended_level}'.", "Assessment would not evidence the intended level."],
            "suggested_lo": f"Rewrite for {intended_level}: Start with a strong {intended_level.lower()}-level verb and specify observable criteria relevant to the module.",
        },
        # 4) Ambiguous due to content coverage — needs context-constrained rewrite
        lambda lo_text, intended_level: {
            "label": "ambiguous",
            "reasons": ["Module content only partially covers the constructs referenced in the LO."],
            "suggested_lo": f"Constrain scope to topics covered in the module and keep the {intended_level.lower()} cognitive demand.",
        },
    ]
    scenario_fn = random.choice(MOCK_ALIGNMENT_SCENARIOS)
    return scenario_fn(lo_text, intended_level)

# Mock questions
def generate_mock_questions(n:int=2)->Dict[str,Any]:
    qs=[]
    for i in range(n):
        qs.append({
            "type":"MCQ_4",
            "stem":f"Mock question {i+1}: What is 2 + 2?",
            "options":[
                {"id":"A","text":"3","option_rationale":"Off-by-one"},
                {"id":"B","text":"4","option_rationale":"Correct"},
                {"id":"C","text":"5","option_rationale":"Common error"},
                {"id":"D","text":"22","option_rationale":"concat digits"},
            ],
            "correct_option_id":"B",
            "cognitive_rationale":"Remember-level math fact",
            "contentReference":"pre-school math"
        })
    return {"questions":qs}

# Mock course outline
def generate_mock_llm_response(course_title:str)->Dict[str,Any]:
    """
    Simulates a call to a Large Language Model.
    Returns a pre-defined, structured JSON response for demonstration.
    """

    # Simulate API call latency
    #time.sleep(5)

    # A detailed mock response that follows the specified JSON schema.
    mock_json = {
      "courseTitle": course_title,
      "courseLevelObjectives": [
        "Analyze the key drivers of public debt vulnerabilities using a structured framework.",
        "Evaluate the effectiveness of fiscal adjustment strategies in stabilizing debt dynamics.",
        "Develop a comprehensive debt management strategy that considers risk and cost trade-offs.",
        "Assess the impact of macroeconomic shocks on debt sustainability."
      ],
      "modules": [
        {
          "moduleTitle": "Foundations of Public Debt Sustainability",
          "overview": "This module introduces the core concepts of public debt sustainability. Learners will explore the main components of the debt dynamic equation and understand how fiscal policy, economic growth, and interest rates interact to determine a country's debt trajectory.",
          "estimatedLearningTime": "2-3 hours",
          "moduleLevelObjectives": [
            {
              "bloomsLevel": "Understand",
              "objectiveText": "Explain the components of the public debt dynamics equation."
            },
            {
              "bloomsLevel": "Analyze",
              "objectiveText": "Differentiate between solvent and sustainable debt paths."
            }
          ],
          "sections": [
            {
              "sectionTitle": "Introduction to Public Debt",
              "linkedModuleObjectives": [
                "Explain the components of the public debt dynamics equation."
              ],
              "units": [
                {
                  "unitTitle": "What is Public Debt?",
                  "keyPoints": [
                    "Definition of public sector debt.",
                    "Common measures and metrics (e.g., Debt-to-GDP ratio)."
                  ],
                  "suggestedFormat": "Text"
                },
                {
                  "unitTitle": "The Government Budget Constraint",
                  "keyPoints": [
                    "Understanding the flow of government revenue and expenditure.",
                    "How deficits lead to debt accumulation."
                  ],
                  "suggestedFormat": "Video"
                }
              ]
            },
            {
              "sectionTitle": "The Debt Dynamics Equation",
              "linkedModuleObjectives": [
                "Explain the components of the public debt dynamics equation."
              ],
              "units": [
                {
                  "unitTitle": "Deconstructing the Equation",
                  "keyPoints": [
                    "Identifying key variables: primary balance, interest rate, growth rate."
                  ],
                  "suggestedFormat": "Interactive"
                },
                {
                  "unitTitle": "Debt-Stabilizing Primary Balance",
                  "keyPoints": [
                    "Calculating the primary balance needed to keep the debt ratio constant."
                  ],
                  "suggestedFormat": "Graphic"
                }
              ]
            },
            {
              "sectionTitle": "Solvency and Sustainability",
              "linkedModuleObjectives": [
                "Differentiate between solvent and sustainable debt paths."
              ],
              "units": [
                {
                  "unitTitle": "Defining Solvency",
                  "keyPoints": [
                    "The government's long-run ability to service its debt."
                  ],
                  "suggestedFormat": "Text"
                },
                {
                  "unitTitle": "Defining Sustainability",
                  "keyPoints": [
                    "Maintaining a stable, non-explosive debt path without major policy shifts.",
                    "[NOTE: This topic was not found in the source material but is included for pedagogical completeness.]"
                  ],
                  "suggestedFormat": "PDF"
                }
              ]
            },
            {
              "sectionTitle": "Module 1 Summary",
              "linkedModuleObjectives": [
                "Explain the components of the public debt dynamics equation.",
                "Differentiate between solvent and sustainable debt paths."
              ],
              "units": [
                {
                  "unitTitle": "Key Takeaways",
                  "keyPoints": [
                    "Recap of the debt dynamics equation.",
                    "Importance of the interest rate-growth differential."
                  ],
                  "suggestedFormat": "Text"
                }
              ]
            }
          ]
        }
      ]
    }
    return json.dumps(mock_json, indent=2)