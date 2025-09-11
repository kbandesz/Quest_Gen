QGenAi is a Streamlit application designed to assist instructional designers and educators in creating high-quality learning objectives (LOs) and assessment questions. It leverages generative AI to analyze LOs against Bloom's Taxonomy, provide suggestions for improvement, and generate aligned multiple-choice questions from your course materials.
 

## Features

* **Upload Course Materials**: Supports various file formats (`.pdf`, `.docx`, `.pptx`, `.txt`).
* **Define and Refine Learning Objectives**: Write your LOs and select the intended Bloom's Taxonomy level.
* **AI-Powered Alignment Check**: Get instant feedback on how well your LOs align with the chosen cognitive level and your course content.
* **Generate Assessment Questions**: Automatically create multiple-choice questions based on your finalized LOs.
* **Export to Word**: Download the generated questions and answers in a `.docx` file for easy integration into your assessments.

## Getting Started

### Prerequisites

* Python 3.8+
* An OpenAI API key

### Installation

1.  Clone the repository:
    ```bash
    git clone [https://github.com/your-username/quest_gen.git](https://github.com/your-username/quest_gen.git)
    cd quest_gen
    ```
2.  Install the required packages:
    ```bash
    pip install -r requirements.txt
    ```
3.  Create a `.env` file in the root directory and add your OpenAI API key:
    ```
    OPENAI_API_KEY="your-api-key-here"
    ```

### Running the Application

```bash
streamlit run mainapp.py
```