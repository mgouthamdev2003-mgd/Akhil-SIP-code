import streamlit as st
import pandas as pd
import plotly.express as px
import yagmail
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh
import logging
import re
from fuzzywuzzy import process, fuzz

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set page configuration
st.set_page_config(page_title="Employee Performance Dashboard", layout="wide")
st.markdown(
    """
    <style>
    .reportview-container {
        background: #E6F2FF;
    }
    .sidebar .sidebar-content {
        background: #2E2E2E;
        color: white;
    }
    .chat-container {
        background: #121212;
        padding: 20px;
        border-radius: 10px;
    }
    .chat-message {
        padding: 10px;
        margin: 5px;
        border-radius: 10px;
        font-family: 'Open Sans', sans-serif;
        font-size: 15px;
    }
    .user-message {
        background-color: #2B7A78;
        color: #FFFFFF;
        text-align: right;
        margin-left: 20%;
    }
    .bot-message {
        background-color: #333333;
        color: #FFFFFF;
        text-align: left;
        margin-right: 20%;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --- Email Setup ---
sender_email = "akhilmiriyala998@gmail.com"
receiver_admin_email = "akhilmiriyala998@gmail.com"
employee_emails = {"1": "akhilmiriyala998@gmail.com"}
yag = yagmail.SMTP(user="akhilmiriyala998@gmail.com", password="vqollmbkelbybdut")

# Title
st.title("Employee Performance Dashboard")
st.markdown("Interactive visualizations of employee performance metrics.")

# Load data from Google Sheets
try:
    sheet_url = "https://docs.google.com/spreadsheets/d/1OxU_4C8zAp_3sqcmj2dnn4YB7N6xcI6PUPLWSG-yl4E/export?format=csv"
    df = pd.read_csv(sheet_url)
    logger.info("Successfully loaded data from Google Sheet.")
except Exception as e:
    st.error(f"Failed to load data from Google Sheet: {str(e)}")
    logger.error(f"Data loading error: {str(e)}")
    df = pd.DataFrame()

# Preprocessing
if not df.empty:
    try:
        df['Hire_Date'] = pd.to_datetime(df['Hire_Date'], errors='coerce')
        df['Years_At_Company'] = (pd.Timestamp.now() - df['Hire_Date']).dt.days / 365.25
        df['Performance_Level'] = pd.cut(df['Performance_Score'], 
                                        bins=[-float('inf'), 1.67, 3.33, float('inf')], 
                                        labels=['Low', 'Medium', 'High'], include_lowest=True)
        df['Satisfaction_Level'] = pd.cut(df['Employee_Satisfaction_Score'], 
                                         bins=[-float('inf'), 1.67, 3.33, float('inf')], 
                                         labels=['Low', 'Medium', 'High'], include_lowest=True)
        df['Retention_Risk_Level'] = pd.cut(df['Retension risk index'], 
                                           bins=[-float('inf'), 0.67, 1.33, float('inf')], 
                                           labels=['Low', 'Medium', 'High'], include_lowest=True)
        df['Remote_Work_Category'] = df['Remote_Work_Frequency'].apply(
            lambda x: 'Work From Office' if x == 0 else 'Work From Home' if x == 100 else 'Hybrid'
        )
        if 'Annual Salary' in df.columns:
            df['Annual Salary'] = df['Annual Salary'].replace('[\$,]', '', regex=True).astype(float)
            logger.info(f"Annual Salary data type: {df['Annual Salary'].dtype}")
        else:
            logger.warning("Annual Salary column not found.")
        if 'Number_of_Projects' not in df.columns:
            logger.warning("Number_of_Projects column not found.")
        if 'Overtime_Hours' not in df.columns:
            logger.warning("Overtime_Hours column not found.")
        logger.info("Preprocessing completed successfully.")
    except Exception as e:
        st.error(f"Error during preprocessing: {str(e)}")
        logger.error(f"Preprocessing error: {str(e)}")

# --- Chatbot Setup ---
# Initialize session state
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'visualization_choice' not in st.session_state:
    st.session_state.visualization_choice = None
if 'last_query' not in st.session_state:
    st.session_state.last_query = None
if 'last_result_df' not in st.session_state:
    st.session_state.last_result_df = None
if 'last_query_info' not in st.session_state:
    st.session_state.last_query_info = None
if 'last_employee_id' not in st.session_state:
    st.session_state.last_employee_id = None

# Intent definitions
intents = [
    {
        'pattern': r'^(hi|hello|hey|hola|howdy)(\s|$)',
        'response': "Hello! I'm here to help with employee data or just chat. What's on your mind?"
    },
    {
        'pattern': r'^good\s+morning(\s|$)',
        'response': "Good morning! Ready to dive into some employee data or just feeling chatty?"
    },
    {
        'pattern': r'^good\s+afternoon(\s|$)',
        'response': "Good afternoon! How can I assist you with employee details or other questions?"
    },
    {
        'pattern': r'^good\s+evening(\s|$)',
        'response': "Good evening! What's up? Want to explore employee data or have a quick chat?"
    },
    {
        'pattern': r'^(how\s+are\s+you|how\'s\s+it\s+going|what\'s\s+up|how\s+you\s+doing|are\s+you\s+okay)(\?|\s|$)',
        'response': "I'm doing great, thanks for asking! Just chilling in the cloud, ready to answer your questions. What's up with you?"
    },
    {
        'pattern': r'^(what\'s\s+the\s+date|today\'s\s+date|current\s+date)(\?|\s|$)',
        'response': "Today is Friday, July 11, 2025."
    },
    {
        'pattern': r'^(what\s+time\s+is\s+it|current\s+time|time\s+now)(\?|\s|$)',
        'response': "It's 12:15 PM IST."
    },
    {
        'pattern': r'^(what\s+day\s+is\s+it|current\s+day|what\'s\s+today)(\?|\s|$)',
        'response': "Today is Friday."
    },
    {
        'pattern': r'^(who\s+are\s+you|what\s+are\s+you|who\s+made\s+you)(\?|\s|$)',
        'response': "I'm Grok, a helpful AI built by xAI. I'm here to answer questions about employee data or have a friendly chat!"
    },
    {
        'pattern': r'^(what\'s\s+your\s+name|your\s+name)(\?|\s|$)',
        'response': "I'm Grok, nice to meet you! What's your name?"
    },
    {
        'pattern': r'^tell\s+me\s+about\s+yourself(\?|\s|$)',
        'response': "I'm Grok, created by xAI. I love crunching data, answering questions, and throwing in a bit of humor. Ask me about employee details or anything else!"
    },
    {
        'pattern': r'^(bye|goodbye|see\s+you|take\s+care|later)(\s|$)',
        'response': "See you later! Feel free to come back anytime."
    },
    {
        'pattern': r'^(thank\s+you|thanks|appreciate\s+it)(\s|$)',
        'response': "You're welcome! Happy to help."
    },
    {
        'pattern': r'^(help|what\s+can\s+you\s+do|how\s+to\s+use|assist\s+me)(\?|\s|$)',
        'response': "I can answer questions about employee data (e.g., 'Employee 123', 'Average salary for analyst') or chat about general stuff like greetings, time, or jokes. Try asking something!"
    },
    {
        'pattern': r'^(what\'s\s+good|sup|yo|how\'s\s+it\s+hanging)(\?|\s|$)',
        'response': "Yo, just hanging out in the digital realm! What's good with you?"
    },
    {
        'pattern': r'^(you\'re\s+awesome|great\s+job|nice\s+work)(\s|$)',
        'response': "Aw, shucks! Thanks for the kind words. What's next?"
    },
    {
        'pattern': r'^(tell\s+me\s+a\s+joke|say\s+something\s+funny)(\?|\s|$)',
        'response': "Why did the computer go to art school? Because it wanted to learn how to draw a better 'byte'!"
    },
    {
        'pattern': r'^(what\'s\s+the\s+weather|weather\s+today)(\?|\s|$)',
        'response': "Sorry, I cannot answer this. I'm not connected to real-time weather data, but I can help with employee info!"
    },
    {
        'pattern': r'^(latest\s+news|news\s+today)(\?|\s|$)',
        'response': "Sorry, I cannot answer this. I don't have access to real-time news, but I can assist with employee data queries!"
    },
    {
        'pattern': r'^(are\s+you\s+happy|are\s+you\s+sad|how\'s\s+your\s+mood)(\?|\s|$)',
        'response': "I'm as happy as a neural network with perfect weights! How about you?"
    },
    {
        'pattern': r'^(why\s+are\s+you\s+here|what\'s\s+your\s+purpose)(\?|\s|$)',
        'response': "I'm here to help you navigate employee data and answer your questions with a dash of fun. What's your purpose today?"
    }
]

# Chatbot functions
def map_keyword_to_column(keyword, columns):
    keyword_map = {
        'department': 'Department', 'dept': 'Department', 'departments': 'Department',
        'job title': 'Job_Title', 'job titles': 'Job_Title', 'jobtitle': 'Job_Title', 'jobtitles': 'Job_Title',
        'gender': 'Gender', 'work mode': 'Remote_Work_Category', 'remote work': 'Remote_Work_Category', 'remote': 'Remote_Work_Category',
        'salary': 'Annual Salary', 'pay': 'Annual Salary', 'wage': 'Annual Salary',
        'performance': 'Performance_Score', 'performance score': 'Performance_Score', 'performance index': 'Performance_Score',
        'satisfaction': 'Employee_Satisfaction_Score', 'satisfaction score': 'Employee_Satisfaction_Score',
        'productivity': 'Productivity score', 'retention': 'Retension risk index', 'retention risk': 'Retension risk index',
        'age': 'Age', 'hire date': 'Hire_Date', 'years at company': 'Years_At_Company',
        'male': 'Gender', 'males': 'Gender', 'female': 'Gender', 'females': 'Gender',
        'employee': 'Employee_ID', 'employees': 'Employee_ID', 'empid': 'Employee_ID', 'employee id': 'Employee_ID', 'emp id': 'Employee_ID',
        'analyst': 'Job_Title', 'analysts': 'Job_Title',
        'total': 'count', 'all': 'no_filter', 'every': 'no_filter', 'everyone': 'no_filter',
        'how many': 'count', 'what are': 'list_unique', 'list': 'list_unique',
        'number of': 'count', 'count': 'count',
        'working hours': 'Overtime_Hours', 'hours': 'Overtime_Hours',
        'projects': 'Number_of_Projects', 'number of projects': 'Number_of_Projects',
        'promotion': 'Number_of_Projects', 'promotions': 'Number_of_Projects', 'promotion rate': 'Number_of_Projects',
        'performance level': 'Performance_Level', 'satisfaction level': 'Satisfaction_Level', 'retention risk level': 'Retention_Risk_Level'
    }
    for key, value in keyword_map.items():
        if key in keyword.lower():
            return value
    keyword = keyword.lower()
    matches = process.extract(keyword, columns, scorer=fuzz.token_sort_ratio)
    best_match, score = matches[0] if matches else (None, 0)
    return best_match if score >= 80 else None

def suggest_chart(query, columns_detected):
    query = query.lower().strip()
    categorical_columns = ['Department', 'Job_Title', 'Gender', 'Remote_Work_Category', 'Performance_Level', 'Satisfaction_Level', 'Retention_Risk_Level']
    numerical_columns = ['Performance_Score', 'Employee_Satisfaction_Score', 'Productivity score', 'Annual Salary', 'Years_At_Company', 'Retension risk index', 'Number_of_Projects', 'Overtime_Hours']
    temporal_columns = ['Hire_Date', 'Years_At_Company']
    
    if any(keyword in query for keyword in ['over time', 'trend', 'year', 'hired', 'years at company']) and any(col in columns_detected for col in temporal_columns):
        return 'line_chart'
    elif any(keyword in query for keyword in ['count', 'number of', 'how many', 'total']):
        if any(col in columns_detected for col in categorical_columns):
            if 'remote work' in query or 'Remote_Work_Category' in columns_detected:
                return 'donut_chart'
            return 'pie_chart'
    elif any(keyword in query for keyword in ['average', 'mean', 'sum', 'max', 'maximum', 'min', 'minimum']):
        if any(col in columns_detected for col in numerical_columns):
            return 'bar_chart'
    elif any(keyword in query for keyword in ['by', 'per', 'wise']) and len([col for col in columns_detected if col in categorical_columns]) >= 2:
        return 'treemap'
    elif 'distribution' in query or any(keyword in query for keyword in ['range', 'spread']) and any(col in columns_detected for col in numerical_columns):
        return 'histogram'
    elif len([col for col in columns_detected if col in numerical_columns]) >= 2:
        return 'scatter_plot'
    elif 'employee' in query or 'empid' in query or any(col in columns_detected for col in ['Employee_ID']):
        return 'table'
    return 'table'

def parse_query(query, columns):
    query = query.lower().strip()
    result = {
        'operation': 'filter',
        'conditions': [],
        'columns': ['Employee_ID'],
        'sort': None,
        'limit': None,
        'agg_func': None,
        'agg_column': None,
        'list_column': None,
        'group_by': None,
        'count_value': None
    }

    # Check if query involves top, bottom, >, or <
    is_top_bottom = 'top' in query or 'bottom' in query or 'highest' in query or 'lowest' in query
    is_comparison = '>' in query or '<' in query
    is_employee_id_query = 'employee id' in query or 'empid' in query or 'emp id' in query

    # Set default columns based on query topic, unless aggregation
    query_keywords = query.lower().split()
    is_aggregation = any(word in query_keywords for word in ['average', 'mean', 'count', 'sum', 'max', 'maximum', 'min', 'minimum', 'how many', 'number of', 'total'])
    if not is_aggregation:
        if any(k in query_keywords for k in ['salary', 'pay', 'wage']):
            result['columns'] = ['Employee_ID', 'Annual Salary']
        elif any(k in query_keywords for k in ['working hours', 'hours', 'overtime']):
            result['columns'] = ['Employee_ID', 'Number_of_Projects', 'Overtime_Hours']
        elif any(k in query_keywords for k in ['satisfaction', 'satisfaction score']):
            result['columns'] = ['Employee_ID', 'Employee_Satisfaction_Score', 'Annual Salary']
        elif any(k in query_keywords for k in ['performance', 'performance score', 'performance index']):
            result['columns'] = ['Employee_ID', 'Performance_Score']
        elif any(k in query_keywords for k in ['promotion', 'promotions', 'promotion rate']):
            result['columns'] = ['Employee_ID', 'Number_of_Projects', 'Years_At_Company']
        elif any(k in query_keywords for k in ['performance level']):
            result['columns'] = ['Employee_ID', 'Performance_Level']
        elif any(k in query_keywords for k in ['satisfaction level']):
            result['columns'] = ['Employee_ID', 'Satisfaction_Level']
        elif any(k in query_keywords for k in ['retention risk level', 'retention level']):
            result['columns'] = ['Employee_ID', 'Retention_Risk_Level']
        elif is_employee_id_query:
            result['columns'] = ['Employee_ID']  # Default for employee ID queries
    else:
        result['columns'] = []  # No default columns for aggregations

    # List unique values or count all employees
    list_patterns = [
        (r'^(list\s+|show\s+|get\s+|what\s+are\s+the\s+|all\s+|total\s+|)(departments?|job\s+titles?|work\s+modes?|remote\s+works?|genders?|performance\s+levels?|satisfaction\s+levels?|retention\s+risk\s+levels?)\b', None),
        (r'^(list\s+|show\s+|get\s+|what\s+are\s+the\s+|all\s+|)(unique\s+|distinct\s+|)(departments?|job\s+titles?|work\s+modes?|remote\s+works?|genders?|performance\s+levels?|satisfaction\s+levels?|retention\s+risk\s+levels?)\b', None),
        (r'^(list\s+|show\s+|get\s+|what\s+are\s+the\s+|all\s+|total\s+|)(employee\s+ids?|employees?|empids?)(?:\s+(in|across|for|)\s*(all\s+|every\s+|)(departments?|dept)?)?\b', 'Employee_ID')
    ]
    for pat, default_col in list_patterns:
        match = re.search(pat, query)
        if match:
            col_keyword = match.group(2) or match.group(3) or 'employee ids'
            col = default_col or map_keyword(col_keyword)
            preposition = match.group(4) if len(match.groups()) > 4 else None
            all_modifier = match.group(5) if len(match.groups()) > 5 else None
            if col:
                if 'count' in query or 'how many' in query or 'number of' in query or 'total' in query:
                    result['operation'] = 'count'
                    result['agg_func'] = 'count'
                    result['columns'] = ['count(employees)']
                else:
                    result['operation'] = 'list_unique'
                    result['list_column'] = col
                    result['columns'] = [col]
                if all_modifier or preposition in ['in', 'across', 'for']:
                    result['conditions'] = []
                break

    # Specific count queries
    if result['operation'] == 'filter':
        count_value_patterns = [
            (r'count\s+of\s+(males?|females?)', 'Gender'),
            (r'how\s+many\s+(males?|females?)', 'Gender'),
            (r'number\s+of\s+(males?|females?)', 'Gender'),
            (r'^(how\s+many\s+|number\s+of\s+|total\s+|count\s+)(employee\s+ids?|employees?|empids?)(?:\s+(in|across|for|)\s*(all\s+|every\s+|)(departments?|dept)?)?\b', 'Employee_ID'),
            (r'^(how\s+many\s+|number\s+of\s+|total\s+|count\s+)(employee\s+ids?|employees?|empids?)\s+(?:with\s+|having\s+|)\b(high|medium|low)\s+(performance\s+level|satisfaction\s+level|retention\s+risk\s+level)\b', 'level')
        ]
        for pat, col in count_value_patterns:
            match = re.search(pat, query)
            if match:
                if col == 'Gender':
                    count_val = match.group(1).rstrip('s').title()
                    if count_val in df['Gender'].unique():
                        result['operation'] = 'count_value'
                        result['agg_column'] = col
                        result['count_value'] = count_val
                        result['columns'] = [f"count({count_val})"]
                elif col == 'Employee_ID':
                    count_val = 'employees'
                    result['operation'] = 'count'
                    result['agg_func'] = 'count'
                    result['columns'] = ['count(employees)']
                    preposition = match.group(3) if len(match.groups()) > 3 else None
                    all_modifier = match.group(4) if len(match.groups()) > 4 else None
                    if all_modifier or preposition in ['in', 'across', 'for']:
                        result['conditions'] = []
                elif col == 'level':
                    count_val = match.group(3).title()
                    level_type = match.group(4).replace(' ', '_').title()
                    if level_type in ['Performance_Level', 'Satisfaction_Level', 'Retention_Risk_Level'] and count_val in ['Low', 'Medium', 'High']:
                        result['operation'] = 'count_value'
                        result['agg_column'] = level_type
                        result['count_value'] = count_val
                        result['columns'] = [f"count({count_val})"]
                break

    # Grouped aggregation
    if result['operation'] == 'filter' and any(phrase in query for word in ['count', 'how many', 'number of', 'total'] for phrase in [f"{word} by", f"{word} per", f"{word}.*wise"]):
        result['operation'] = 'group_aggregate'
        result['agg_func'] = 'count'
        for col in columns:
            if col.lower() in query or map_keyword(col.lower()) == col:
                result['group_by'] = col
                result['columns'] = [col, 'Count']
                break
        if not result['group_by']:
            for keyword in ['department', 'gender', 'job title', 'work mode', 'remote work', 'performance level', 'satisfaction level', 'retention risk level']:
                matched = map_keyword(keyword)
                if matched:
                    result['group_by'] = matched
                    result['columns'] = [matched, 'Count']
                    break

    # General aggregation with conditions
    if result['operation'] == 'filter' and any(word in query for word in ['average', 'mean', 'count', 'sum', 'max', 'maximum', 'min', 'minimum', 'how many', 'number of', 'total']):
        result['operation'] = 'aggregate'
        if 'average' in query or 'mean' in query:
            result['agg_func'] = 'mean'
        elif 'count' in query or 'how many' in query or 'number of' in query or 'total' in query:
            result['agg_func'] = 'count'
        elif 'sum' in query:
            result['agg_func'] = 'sum'
        elif 'max' in query or 'maximum' in query:
            result['agg_func'] = 'max'
        elif 'min' in query or 'minimum' in query:
            result['agg_func'] = 'min'
        
        agg_keywords = [
            ('salary', 'Annual Salary'),
            ('age', 'Age'),
            ('performance', 'Performance_Score'),
            ('satisfaction', 'Employee_Satisfaction_Score'),
            ('productivity', 'Productivity score'),
            ('years at company', 'Years_At_Company'),
            ('working hours', 'Overtime_Hours'),
            ('projects', 'Number_of_Projects')
        ]
        for keyword, col in agg_keywords:
            if keyword in query:
                result['agg_column'] = col
                break
        if not result['agg_column']:
            for col in columns:
                if col.lower() in query or map_keyword(query) == col:
                    result['agg_column'] = col
                    break

        # Handle job role filter for aggregation
        job_role_match = re.search(r'(?:for|of|in|with|as)\s+([\w\s]+?)(?:\s+job\s+role|\b)', query)
        if job_role_match:
            job_role = job_role_match.group(1).strip().title()
            result['conditions'].append(('Job_Title', 'contains', job_role))
            if 'Job_Title' not in result['columns']:
                result['columns'].append('Job_Title')

    # Complex filter conditions with prepositions and level columns
    complex_patterns = [
        (r'(?:in|across|for|of)\s+([\w\s&]+)\s*(department|dept)', 'Department', '=='),
        (r'gender\s+(\w+)', 'Gender', '=='),
        (r'job\s+title\s+([\w\s]+)', 'Job_Title', '=='),
        (r'(analysts?)', 'Job_Title', 'contains'),
        (r'age\s*>\s*(\d+)', 'Age', '>'),
        (r'age\s*<\s*(\d+)', 'Age', '<'),
        (r'age\s+(\d+)', 'Age', '=='),
        (r'salary\s*>\s*([\d,]+)', 'Annual Salary', '>'),
        (r'salary\s*<\s*([\d,]+)', 'Annual Salary', '<'),
        (r'salary\s*=\s*([\d,]+)', 'Annual Salary', '=='),
        (r'performance score\s*>\s*(\d+)', 'Performance_Score', '>'),
        (r'performance score\s*<\s*(\d+)', 'Performance_Score', '<'),
        (r'performance score\s+(\d+)', 'Performance_Score', '=='),
        (r'hired after\s+(\d{4})', 'Hire_Date', '>'),
        (r'hired before\s+(\d{4})', 'Hire_Date', '<'),
        (r'hired between\s+(\d{4}-\d{2}-\d{2})\s+and\s+(\d{4}-\d{2}-\d{2})', 'Hire_Date', 'between'),
        (r'(high|medium|low)\s+(performance\s+level|satisfaction\s+level|retention\s+risk\s+level)', None, 'level')
    ]
    for pat, col, op in complex_patterns:
        match = re.search(pat, query)
        if match:
            if op == 'level':
                level_val = match.group(1).title()
                level_col = match.group(2).replace(' ', '_').title()
                if level_col in ['Performance_Level', 'Satisfaction_Level', 'Retention_Risk_Level'] and level_val in ['Low', 'Medium', 'High']:
                    result['conditions'].append((level_col, '==', level_val))
                    if level_col not in result['columns']:
                        result['columns'].append(level_col)
            elif op == 'between':
                start_date = pd.to_datetime(match.group(1))
                end_date = pd.to_datetime(match.group(2))
                result['conditions'].append((col, 'between', (start_date, end_date)))
            else:
                val = match.group(1).strip().title() if op in ['==', 'contains'] and col not in ['Age', 'Performance_Score', 'Hire_Date', 'Annual Salary'] else \
                      pd.to_datetime(f"{match.group(1)}-01-01") if col == 'Hire_Date' else \
                      float(match.group(1).replace(',', '')) if col == 'Annual Salary' else int(match.group(1))
                result['conditions'].append((col, op, val))
            if col and col not in result['columns'] and not is_aggregation:
                result['columns'].append(col)
            # Ensure Employee_ID is included for >, <, or employee id queries
            if (op in ['>', '<'] or is_comparison or is_employee_id_query) and not is_aggregation and 'Employee_ID' not in result['columns']:
                result['columns'].insert(0, 'Employee_ID')

    # Department-wise top N employees
    if result['operation'] == 'filter' and any(phrase in query for phrase in ['each department', 'by department', 'department wise', 'per department', 'in each department']):
        result['operation'] = 'group_top'
        result['group_by'] = 'Department'
        limit_match = re.search(r'(top|highest)\s+(\d+)', query)
        result['limit'] = int(limit_match.group(2)) if limit_match else 5
        result['sort_column'] = 'Performance_Score'
        for col in ['Performance_Score', 'Annual Salary', 'Employee_Satisfaction_Score', 'Productivity score', 'Number_of_Projects', 'Overtime_Hours']:
            if col.lower() in query or map_keyword(col.lower()) == col:
                result['sort_column'] = col
                break
        result['sort'] = 'desc'
        result['columns'] = ['Employee_ID', 'Department', 'Job_Title', result['sort_column']]

    # Sorting (non-grouped top/bottom)
    if result['operation'] == 'filter' and ('top' in query or 'highest' in query):
        result['operation'] = 'sort'
        result['sort'] = 'desc'
        limit_match = re.search(r'(top|highest)\s+(\d+)', query)
        result['limit'] = int(limit_match.group(2)) if limit_match else 5
        for col in columns:
            if col.lower() in query or map_keyword(query) == col:
                result['sort_column'] = col
                break
        if not result['sort_column']:
            for keyword in ['performance', 'salary', 'satisfaction', 'productivity', 'working hours', 'projects', 'promotion']:
                matched = map_keyword(keyword)
                if matched:
                    result['sort_column'] = matched
                    break
        # Ensure Employee_ID is included for top queries
        if 'Employee_ID' not in result['columns']:
            result['columns'].insert(0, 'Employee_ID')
    elif result['operation'] == 'filter' and ('bottom' in query or 'lowest' in query):
        result['operation'] = 'sort'
        result['sort'] = 'asc'
        limit_match = re.search(r'(bottom|lowest)\s+(\d+)', query)
        result['limit'] = int(limit_match.group(2)) if limit_match else 5
        for col in columns:
            if col.lower() in query or map_keyword(query) == col:
                result['sort_column'] = col
                break
        if not result['sort_column']:
            for keyword in ['performance', 'salary', 'satisfaction', 'productivity', 'working hours', 'projects', 'promotion']:
                matched = map_keyword(keyword)
                if matched:
                    result['sort_column'] = matched
                    break
        # Ensure Employee_ID is included for bottom queries
        if 'Employee_ID' not in result['columns']:
            result['columns'].insert(0, 'Employee_ID')

    return result

def process_query(df, query_info):
    filtered_df = df.copy()
    for col, op, val in query_info['conditions']:
        if op == '==':
            filtered_df = filtered_df[filtered_df[col] == val]
        elif op == '>':
            filtered_df = filtered_df[filtered_df[col] > val]
        elif op == '<':
            filtered_df = filtered_df[filtered_df[col] < val]
        elif op == 'between':
            start_date, end_date = val
            filtered_df = filtered_df[(filtered_df[col] >= start_date) & (filtered_df[col] <= end_date)]
        elif op == 'contains':
            filtered_df = filtered_df[filtered_df[col].str.contains(val, case=False, na=False)]
    if query_info['operation'] == 'count_value':
        agg_col = query_info.get('agg_column')
        count_val = query_info.get('count_value')
        if agg_col and count_val:
            count = len(filtered_df[filtered_df[agg_col] == count_val])
            return pd.DataFrame({f"count({count_val})": [count]})
        return pd.DataFrame({"Error": ["No valid column or value for counting"]})
    if query_info['operation'] == 'aggregate':
        agg_col = query_info.get('agg_column')
        agg_func = query_info.get('agg_func')
        if agg_col and agg_func:
            if agg_func == 'count':
                result = len(filtered_df)
                return pd.DataFrame({f"count(employees)": [result]})
            filtered_df[agg_col] = pd.to_numeric(filtered_df[agg_col], errors='coerce')
            result = filtered_df[agg_col].agg(agg_func)
            return pd.DataFrame({f"{agg_func}({agg_col})": [result]})
        return pd.DataFrame({"Error": ["No valid column for aggregation"]})
    if query_info['operation'] == 'group_aggregate':
        group_col = query_info.get('group_by')
        agg_func = query_info.get('agg_func')
        if group_col and agg_func:
            if agg_func == 'count':
                result = filtered_df[group_col].value_counts().reset_index()
                result.columns = [group_col, 'Count']
                return result
        return pd.DataFrame({"Error": ["No valid column for grouping"]})
    if query_info['operation'] == 'list_unique':
        list_col = query_info.get('list_column')
        if list_col:
            unique_values = sorted(filtered_df[list_col].dropna().unique())
            return pd.DataFrame({list_col: unique_values})
        return pd.DataFrame({"Error": ["No valid column for listing"]})
    if query_info['operation'] == 'group_top':
        group_col = query_info.get('group_by')
        sort_col = query_info.get('sort_column')
        limit = query_info.get('limit', 5)
        if group_col and sort_col:
            filtered_df[sort_col] = pd.to_numeric(filtered_df[sort_col], errors='coerce')
            result = filtered_df.groupby(group_col).apply(
                lambda x: x.nlargest(limit, sort_col, keep='all')
            ).reset_index(drop=True)
            return result[query_info['columns']]
        return pd.DataFrame({"Error": ["No valid column for grouping or sorting"]})
    if query_info['operation'] == 'sort':
        sort_col = query_info.get('sort_column')
        if sort_col:
            filtered_df[sort_col] = pd.to_numeric(filtered_df[sort_col], errors='coerce')
            filtered_df = filtered_df.sort_values(
                by=sort_col,
                ascending=(query_info['sort'] == 'asc')
            )
            if query_info['limit']:
                filtered_df = filtered_df.head(query_info['limit'])
            return filtered_df[query_info['columns']].reset_index(drop=True)
    if query_info['operation'] == 'filter':
        if query_info['columns']:
            filtered_df = filtered_df[query_info['columns']]
        return filtered_df.reset_index(drop=True) if not filtered_df.empty else pd.DataFrame({"Message": ["No results found."]})
    return pd.DataFrame({"Error": ["Unable to understand your query. Try again."]})

def get_chatbot_response(user_input, df, columns):
    user_input = user_input.lower().strip()
    st.session_state.last_query = user_input

    # Check conversation history for context
    recent_history = [chat for chat in st.session_state.chat_history[-6:] if chat['role'] == 'user'][-3:]  # Last 3 user messages
    context_keywords = []
    context_employee_id = None
    for chat in recent_history:
        context_keywords.extend(chat['message'].lower().split())
        emp_id_match = re.search(r'(?:employee|emp\s*id|employee\s*id)\s*(\d+)', chat['message'])
        if emp_id_match:
            context_employee_id = emp_id_match.group(1)

    # Check for intents
    for intent in intents:
        if re.match(intent['pattern'], user_input, re.IGNORECASE):
            response = intent['response']
            if recent_history:
                response = f"Following our chat, {response.lower()[0] + response[1:]}"
            st.session_state.chat_history.append({"role": "bot", "message": response})
            return response, None, None, None

    # Check for follow-up questions
    is_follow_up = any(keyword in user_input for keyword in ['more', 'details', 'further', 'tell me more'])
    emp_id_match = re.search(r'(?:employee|emp\s*id|employee\s*id)\s*(\d+)', user_input)
    if is_follow_up and st.session_state.last_result_df is not None:
        if emp_id_match and emp_id_match.group(1) == st.session_state.last_employee_id:
            # Provide more details for the same employee
            emp_id = emp_id_match.group(1)
            emp_data = df[df['Employee_ID'] == emp_id]
            if not emp_data.empty:
                row = emp_data.iloc[0]
                additional_columns = ['Annual Salary', 'Number_of_Projects', 'Overtime_Hours', 'Years_At_Company']
                available_columns = [col for col in additional_columns if col in df.columns]
                response = f"Following up on Employee {emp_id}, here are more details:\n"
                for col in available_columns:
                    response += f"{col.replace('_', ' ')}: {row[col]}\n"
                st.session_state.chat_history.append({"role": "bot", "message": response})
                # Show a visualization
                if 'Annual Salary' in available_columns and 'Number_of_Projects' in available_columns:
                    metrics = pd.DataFrame({
                        'Metric': ['Annual Salary', 'Number of Projects'],
                        'Value': [row['Annual Salary'], row['Number_of_Projects']]
                    })
                    fig = px.bar(metrics, x='Metric', y='Value', title=f"Additional Metrics for Employee {emp_id}",
                                 color_discrete_sequence=['#2B7A78'])
                    st.plotly_chart(fig, use_container_width=True)
                return response, None, None, None
            else:
                response = f"No additional details found for Employee {emp_id}."
                st.session_state.chat_history.append({"role": "bot", "message": response})
                return response, None, None, None
        elif st.session_state.last_query_info:
            # Expand columns for previous query
            query_info = st.session_state.last_query_info.copy()
            result_df = st.session_state.last_result_df
            if 'Employee_ID' in result_df.columns:
                new_columns = ['Employee_ID', 'Department', 'Job_Title', 'Annual Salary', 'Number_of_Projects', 'Overtime_Hours']
                new_columns = [col for col in new_columns if col in df.columns and col not in query_info['columns']]
                query_info['columns'].extend(new_columns[:2])  # Add up to 2 new columns
                result_df = process_query(df, query_info)
                if not result_df.empty and 'Error' not in result_df.columns:
                    response = f"Following up on your previous query, here are more details: Found {len(result_df)} employees."
                    st.session_state.chat_history.append({"role": "bot", "message": response})
                    st.dataframe(result_df)
                    return response, query_info, result_df, suggest_chart(user_input, query_info['columns'])
                else:
                    response = "Sorry, I cannot provide more details for this query."
                    st.session_state.chat_history.append({"role": "bot", "message": response})
                    return response, None, None, None
        else:
            response = "Sorry, I cannot provide more details. Please specify what you're looking for."
            st.session_state.chat_history.append({"role": "bot", "message": response})
            return response, None, None, None

    # Check for context-related queries (e.g., same topic as previous)
    context_related = False
    if recent_history:
        for keyword in context_keywords:
            if keyword in user_input and keyword not in ['employee', 'emp', 'id', 'more', 'details', 'further']:
                context_related = True
                break

    # Handle specific employee ID queries
    emp_id_patterns = [
        r'(?:employee|emp\s*id|employee\s*id)\s*(\d+)',  # Matches "employee 123", "emp id 123", "employee id 123"
        r'details\s*for\s*(?:employee|emp\s*id|employee\s*id)\s*(\d+)',  # Matches "details for employee 123"
        r'info\s*(?:on|for)\s*(?:employee|emp\s*id|employee\s*id)\s*(\d+)'  # Matches "info on employee 123"
    ]
    for pattern in emp_id_patterns:
        match = re.search(pattern, user_input)
        if match:
            emp_id = match.group(1)
            try:
                emp_data = df[df['Employee_ID'] == emp_id]
                if not emp_data.empty:
                    row = emp_data.iloc[0]
                    response = (f"Employee ID: {emp_id}\n"
                                f"Department: {row['Department']}\n"
                                f"Job Title: {row['Job_Title']}\n"
                                f"Performance Level: {row['Performance_Level']}\n"
                                f"Satisfaction Level: {row['Satisfaction_Level']}\n"
                                f"Retention Risk Level: {row['Retention_Risk_Level']}\n"
                                f"Remote Work: {row['Remote_Work_Category']}")
                    if context_employee_id == emp_id:
                        response = f"Continuing our discussion about Employee {emp_id}, here are the details:\n{response}"
                    elif context_related:
                        response = f"Moving on from our previous chat, here are details for Employee {emp_id}:\n{response}"
                    st.session_state.last_employee_id = emp_id
                    st.session_state.chat_history.append({"role": "bot", "message": response})
                    metrics = pd.DataFrame({
                        'Metric': ['Performance Score', 'Satisfaction Score'],
                        'Value': [row['Performance_Score'], row['Employee_Satisfaction_Score']]
                    })
                    fig = px.bar(metrics, x='Metric', y='Value', title=f"Employee {emp_id} Metrics",
                                 color_discrete_sequence=['#2B7A78'])
                    st.plotly_chart(fig, use_container_width=True)
                    return response, None, None, None
                else:
                    response = f"No employee found with ID {emp_id}. Please check the ID or try another query."
                    st.session_state.chat_history.append({"role": "bot", "message": response})
                    return response, None, None, None
            except Exception as e:
                logger.error(f"Error in employee query: {str(e)}")
                response = f"Error processing employee query: {str(e)}. Try again with a valid Employee ID."
                st.session_state.chat_history.append({"role": "bot", "message": response})
                return response, None, None, None

    # Handle general queries
    try:
        query_info = parse_query(user_input, columns)
        result_df = process_query(df, query_info)
        if result_df.empty or 'Error' in result_df.columns or 'Message' in result_df.columns:
            error_msg = result_df.get('Error', [''])[0] or result_df.get('Message', [''])[0]
            suggestion = "Try queries like 'Employee 123', 'Employee ID with salary > 90000', 'List departments', 'Count of males', 'Average salary for analyst', or 'Employees with high performance level'."
            response = f"Sorry, I cannot understand or answer this question. {suggestion}"
            st.session_state.chat_history.append({"role": "bot", "message": response})
            return response, None, None, None
        
        chart_type = suggest_chart(user_input, query_info['columns'])
        response = ""
        
        if query_info['operation'] == 'list_unique':
            list_col = query_info.get('list_column')
            response = f"Unique {list_col}: {', '.join(map(str, result_df[list_col]))}"
        elif query_info['operation'] == 'count_value':
            agg_col = query_info.get('agg_column')
            count_val = query_info.get('count_value')
            count = result_df[f"count({count_val})"].iloc[0]
            response = f"Count of {count_val}: {count}"
        elif query_info['operation'] == 'group_aggregate':
            group_col = query_info.get('group_by')
            counts = result_df.set_index(group_col)['Count'].to_dict()
            response = f"Count by {group_col}: {', '.join([f'{k}: {v}' for k, v in counts.items()])}"
        elif query_info['operation'] == 'aggregate':
            agg_col = query_info.get('agg_column')
            agg_func = query_info.get('agg_func')
            value = result_df[f"{agg_func}({agg_col})"].iloc[0]
            response = f"{agg_func.capitalize()} of {agg_col}: {value:.2f}"
        elif query_info['operation'] == 'group_top':
            group_col = query_info.get('group_by')
            sort_col = query_info.get('sort_column')
            response = f"Top employees by {sort_col} per {group_col} displayed in table and chart."
        else:
            response = f"Found {len(result_df)} employees matching the criteria."
        
        if context_related:
            response = f"Following up on your previous interest in similar topics, {response.lower()[0] + response[1:]}"
        elif recent_history:
            response = f"Moving on from our previous chat, {response.lower()[0] + response[1:]}"
        
        st.session_state.last_result_df = result_df
        st.session_state.last_query_info = query_info
        st.session_state.chat_history.append({"role": "bot", "message": response})
        st.dataframe(result_df)
        return response, query_info, result_df, chart_type
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        response = "Sorry, I cannot understand or answer this question. Try something like 'Employee 123', 'Average salary for analyst', or 'Hello'."
        st.session_state.chat_history.append({"role": "bot", "message": response})
        return response, None, None, None

# Sidebar: Filters
st.sidebar.header("Filters")
departments = df['Department'].dropna().unique().tolist() if not df.empty else []
job_titles = df['Job_Title'].dropna().unique().tolist() if not df.empty else []
remote_options = ['All', 'Work From Home', 'Work From Office', 'Hybrid']
employee_ids = ['All'] + df['Employee_ID'].dropna().astype(str).unique().tolist() if not df.empty else ['All']
selected_employee = st.sidebar.selectbox("Select Employee ID", employee_ids)
selected_department = st.sidebar.selectbox("Select Department", ["All"] + departments)
selected_job = st.sidebar.selectbox("Select Job Title", ["All"] + job_titles)
selected_remote = st.sidebar.selectbox("Select Remote Work Type", remote_options)
date_range = st.sidebar.date_input("Filter by Hire Date Range", [df['Hire_Date'].min(), df['Hire_Date'].max()] if not df.empty else [datetime.now(), datetime.now()])

# Apply filters
filtered_df = df.copy() if not df.empty else pd.DataFrame()
if not filtered_df.empty:
    try:
        if selected_employee != "All":
            filtered_df = filtered_df[filtered_df['Employee_ID'] == selected_employee]
        if selected_department != "All":
            filtered_df = filtered_df[filtered_df['Department'] == selected_department]
        if selected_job != "All":
            filtered_df = filtered_df[filtered_df['Job_Title'] == selected_job]
        if selected_remote != "All":
            filtered_df = filtered_df[filtered_df['Remote_Work_Category'] == selected_remote]
        if len(date_range) == 2:
            filtered_df = filtered_df[(filtered_df['Hire_Date'] >= pd.to_datetime(date_range[0])) &
                                      (filtered_df['Hire_Date'] <= pd.to_datetime(date_range[1]))]
        logger.info(f"Filtered data to {len(filtered_df)} rows.")
    except Exception as e:
        st.error(f"Error applying filters: {str(e)}")
        logger.error(f"Filter error: {str(e)}")

# Email Alerts
st.subheader("Email Notifications")
if st.button("Send Email Alerts"):
    low_sat_df = df[df['Satisfaction_Level'] == 'Low'] if not df.empty else pd.DataFrame()
    low_sat_content = "\n".join([f"Low Satisfaction - EmpID: {row['Employee_ID']}, Dept: {row['Department']}, Job: {row['Job_Title']}" for _, row in low_sat_df.iterrows()]) if not low_sat_df.empty else "None"
    low_perf_df = df[df['Performance_Level'] == 'Low'] if not df.empty else pd.DataFrame()
    low_perf_content = "\n".join([f"Low Performance - EmpID: {row['Employee_ID']}, Dept: {row['Department']}, Job: {row['Job_Title']}" for _, row in low_perf_df.iterrows()]) if not low_perf_df.empty else "None"
    high_ret_df = df[df['Retention_Risk_Level'] == 'High'] if not df.empty else pd.DataFrame()
    high_ret_content = "\n".join([f"High Retention Risk - EmpID: {row['Employee_ID']}, Dept: {row['Department']}, Job: {row['Job_Title']}" for _, row in high_ret_df.iterrows()]) if not high_ret_df.empty else "None"
    email_content = f"Employee Alerts:\n\nLow Satisfaction Alerts:\n{low_sat_content}\n\nLow Performance Alerts:\n{low_perf_content}\n\nHigh Retention Risk Alerts:\n{high_ret_content}"
    if low_sat_content != "None" or low_perf_content != "None" or high_ret_content != "None":
        try:
            yag.send(to=receiver_admin_email, subject="🚨 Employee Alerts", contents=email_content)
            st.success("✅ Admin alert email sent.")
            logger.info("Email alert sent successfully.")
        except Exception as e:
            st.error(f"Failed to send email: {str(e)}")
            logger.error(f"Email sending error: {str(e)}")
    else:
        st.info("ℹ️ No email alerts sent. No employees meet alert criteria.")

# Alert Display Buttons
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("View Low Satisfaction Alerts"):
        st.write("**Low Satisfaction Alerts**")
        st.dataframe(low_sat_df[['Employee_ID', 'Department', 'Job_Title']] if 'low_sat_df' in locals() else pd.DataFrame())
with col2:
    if st.button("View Low Performance Alerts"):
        st.write("**Low Performance Alerts**")
        st.dataframe(low_perf_df[['Employee_ID', 'Department', 'Job_Title']] if 'low_perf_df' in locals() else pd.DataFrame())
with col3:
    if st.button("View High Retention Risk Alerts"):
        st.write("**High Retention Risk Alerts**")
        st.dataframe(high_ret_df[['Employee_ID', 'Department', 'Job_Title']] if 'high_ret_df' in locals() else pd.DataFrame())

# KPI Cards
remote_efficiency_column = next((col for col in df.columns if col.lower().replace(" ", "_") == 'remote_work_efficiency'), None)
remote_work_efficiency_avg = filtered_df[remote_efficiency_column].mean() if not filtered_df.empty and remote_efficiency_column else 0
productivity_avg = filtered_df['Productivity score'].mean() if not filtered_df.empty else 0
avg_salary = filtered_df['Annual Salary'].mean() if 'Annual Salary' in filtered_df.columns and not filtered_df.empty else 0
num_employees = len(filtered_df)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f"""
        <div style="background-color:black; padding:20px; border-radius:10px">
            <h3 style="color:white; text-align:center;">Remote Work Efficiency</h3>
            <h1 style="color:white; text-align:center;">{remote_work_efficiency_avg:.2f}</h1>
        </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown(f"""
        <div style="background-color:black; padding:20px; border-radius:10px">
            <h3 style="color:white; text-align:center;">Productivity Score</h3>
            <h1 style="color:white; text-align:center;">{productivity_avg:.2f}</h1>
        </div>
    """, unsafe_allow_html=True)
with col3:
    st.markdown(f"""
        <div style="background-color:black; padding:20px; border-radius:10px">
            <h3 style="color:white; text-align:center;">Average Annual Salary</h3>
            <h1 style="color:white; text-align:center;">${avg_salary:,.2f}</h1>
        </div>
    """, unsafe_allow_html=True)
with col4:
    st.markdown(f"""
        <div style="background-color:black; padding:20px; border-radius:10px">
            <h3 style="color:white; text-align:center;">Number of Employees</h3>
            <h1 style="color:white; text-align:center;">{num_employees}</h1>
        </div>
    """, unsafe_allow_html=True)

# Visual Analytics
st.subheader("Visual Analytics")
row1_col1, row1_col2, row1_col3 = st.columns(3)
with row1_col1:
    st.markdown("**Remote Work Efficiency by Department**")
    remote_efficiency = filtered_df.groupby(['Department', 'Remote_Work_Category'])['Productivity score'].mean().reset_index() if not filtered_df.empty else pd.DataFrame()
    fig_remote = px.bar(remote_efficiency, x='Department', y='Productivity score', color='Remote_Work_Category',
                        barmode='group', color_discrete_map={'Work From Home': '#2B7A78', 'Work From Office': '#333333', 'Hybrid': '#228B22'}) if not remote_efficiency.empty else px.bar()
    st.plotly_chart(fig_remote, use_container_width=True)
with row1_col2:
    st.markdown("**Performance Level Distribution by Job Title**")
    tree_data = filtered_df.groupby(['Job_Title', 'Performance_Level'])['Employee_ID'].count().reset_index() if not filtered_df.empty else pd.DataFrame()
    tree_data.rename(columns={'Employee_ID': 'Number_of_Employees'}, inplace=True)
    # ... (Your code *before* line 909) ...

# --- START: Add the new recommended solution here (around line 909) ---

# 1. Create a copy to avoid modifying the original dataframe in cache
tree_data_copy = tree_data.copy()

# 2. Fill NaN values in the columns used in the 'path' and 'color'
tree_data_copy['Job_Title'] = tree_data_copy['Job_Title'].fillna('Unknown Job Title')
tree_data_copy['Performance_Level'] = tree_data_copy['Performance_Level'].fillna('Unknown')

# 3. (Optional, but safe) Force the columns to be 'str' type
tree_data_copy['Job_Title'] = tree_data_copy['Job_Title'].astype(str)
tree_data_copy['Performance_Level'] = tree_data_copy['Performance_Level'].astype(str)

# 4. Update your color map to handle the new 'Unknown' category
color_map = {
    'Low': '#FF4040', 
    'Medium': '#FFA500', 
    'High': '#228B22',
    'Unknown': '#808080'  # Add a grey color for unknown data
}
fig_tree = px.treemap(tree_data, path=['Job_Title', 'Performance_Level'], values='Number_of_Employees',
                          color='Performance_Level',
                          color_discrete_map={'Low': '#FF4040', 'Medium': '#FFA500', 'High': '#228B22'}) if not tree_data.empty else px.treemap()
    st.plotly_chart(fig_tree, use_container_width=True)
with row1_col3:
    st.markdown("**Employee Count by Retention Risk Level and Job Title**")
    retention_count = filtered_df.groupby(['Job_Title', 'Retention_Risk_Level'])['Employee_ID'].count().reset_index() if not filtered_df.empty else pd.DataFrame()
    retention_count.rename(columns={'Employee_ID': 'Number_of_Employees'}, inplace=True)
    fig_ret = px.bar(retention_count, x='Job_Title', y='Number_of_Employees', color='Retention_Risk_Level',
                     color_discrete_map={'Low': '#8B0000', 'Medium': '#FFA500', 'High': '#006400'}) if not retention_count.empty else px.bar()
    st.plotly_chart(fig_ret, use_container_width=True)

row2_col1, row2_col2, row2_col3 = st.columns(3)
with row2_col1:
    st.markdown("**Remote Work Type Distribution**")
    remote_data = filtered_df['Remote_Work_Category'].value_counts().reset_index() if not filtered_df.empty else pd.DataFrame()
    remote_data.columns = ['Remote_Work_Category', 'Count']
    fig_pie = px.pie(remote_data, names='Remote_Work_Category', values='Count',
                     color_discrete_map={'Work From Home': '#2B7A78', 'Work From Office': '#333333', 'Hybrid': '#228B22'}) if not remote_data.empty else px.pie()
    st.plotly_chart(fig_pie, use_container_width=True)
with row2_col2:
    st.markdown("**Average Satisfaction by Department**")
    sat_avg = filtered_df.groupby('Department')['Employee_Satisfaction_Score'].mean().reset_index() if not filtered_df.empty else pd.DataFrame()
    fig_sat = px.bar(sat_avg, x='Department', y='Employee_Satisfaction_Score',
                     color='Department', color_discrete_sequence=px.colors.qualitative.Plotly) if not sat_avg.empty else px.bar()
    st.plotly_chart(fig_sat, use_container_width=True)
with row2_col3:
    st.markdown("**Performance Trend by Years at Company**")
    filtered_df['Years_Bin'] = pd.cut(filtered_df['Years_At_Company'], bins=10).apply(lambda x: x.mid) if not filtered_df.empty else pd.Series()
    trend_data = filtered_df.groupby(['Years_Bin', 'Job_Title'])['Performance_Score'].mean().reset_index() if not filtered_df.empty else pd.DataFrame()
    fig_line = px.line(trend_data, x='Years_Bin', y='Performance_Score', color='Job_Title') if not trend_data.empty else px.line()
    st.plotly_chart(fig_line, use_container_width=True)

# Data Alert Tables
st.subheader("Data Alerts")
alert_dept = st.selectbox("Filter Alerts by Department", ["All"] + departments, key="alert_dept")
alert_job = st.selectbox("Filter Alerts by Job Title", ["All"] + job_titles, key="alert_job")
low_sat_alert_df = df[df['Satisfaction_Level'] == 'Low'][['Employee_ID', 'Department', 'Job_Title']] if not df.empty else pd.DataFrame()
high_ret_alert_df = df[df['Retention_Risk_Level'] == 'High'][['Employee_ID', 'Department', 'Job_Title']] if not df.empty else pd.DataFrame()
if alert_dept != "All":
    low_sat_alert_df = low_sat_alert_df[low_sat_alert_df['Department'] == alert_dept] if not low_sat_alert_df.empty else pd.DataFrame()
    high_ret_alert_df = high_ret_alert_df[high_ret_alert_df['Department'] == alert_dept] if not high_ret_alert_df.empty else pd.DataFrame()
if alert_job != "All":
    low_sat_alert_df = low_sat_alert_df[low_sat_alert_df['Job_Title'] == alert_job] if not low_sat_alert_df.empty else pd.DataFrame()
    high_ret_alert_df = high_ret_alert_df[high_ret_alert_df['Job_Title'] == alert_job] if not high_ret_alert_df.empty else pd.DataFrame()
col1, col2 = st.columns(2)
with col1:
    st.markdown("**Low Satisfaction Alerts**")
    st.dataframe(low_sat_alert_df, use_container_width=True)
with col2:
    st.markdown("**High Retention Risk Alerts**")
    st.dataframe(high_ret_alert_df, use_container_width=True)

# Chatbot Section
st.subheader("Chatbot")
st.markdown("Ask about employee details (e.g., 'Employee 123', 'Employee ID with salary > 90000', 'Average salary for analyst'), greetings (e.g., 'Hello', 'Good morning'), or general questions (e.g., 'What's the time?', 'Tell me a joke').")
# Display chat history in a container
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for chat in st.session_state.chat_history:
    if chat['role'] == 'user':
        st.markdown(f"<div class='chat-message user-message'>{chat['message']}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='chat-message bot-message'>{chat['message']}</div>", unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

user_input = st.text_input("Type your question:", key="chat_input")
if user_input:
    st.session_state.chat_history.append({"role": "user", "message": user_input})
    columns = df.columns.tolist() if not df.empty else []
    response, query_info, result_df, chart_type = get_chatbot_response(user_input, filtered_df, columns)
    
    # Show visualization choice if query produced a result_df
    if result_df is not None and not result_df.empty and 'Error' not in result_df.columns and 'Message' not in result_df.columns:
        st.markdown("Would you like a visualization for this result?")
        visualization_choice = st.radio(
            "Select an option:",
            ["Yes", "No"],
            key=f"vis_choice_{user_input}",
            index=0
        )
        st.session_state.visualization_choice = visualization_choice
        
        if visualization_choice == "No":
            st.session_state.chat_history.append({"role": "bot", "message": "Thank you for saving our efforts"})
            st.markdown("<div class='chat-message bot-message'>Thank you for saving our efforts</div>", unsafe_allow_html=True)
        elif visualization_choice == "Yes":
            if chart_type != 'table' or query_info['operation'] in ['list_unique', 'count_value', 'group_aggregate', 'aggregate', 'group_top']:
                if query_info['operation'] == 'list_unique':
                    list_col = query_info.get('list_column')
                    if chart_type == 'pie_chart':
                        fig = px.pie(result_df, names=list_col, title=f"Distribution of {list_col}",
                                     color_discrete_sequence=px.colors.qualitative.Plotly)
                    elif chart_type == 'donut_chart':
                        fig = px.pie(result_df, names=list_col, title=f"Distribution of {list_col}", hole=0.4,
                                     color_discrete_sequence=px.colors.qualitative.Plotly)
                    else:
                        fig = px.bar(result_df, x=list_col, title=f"Unique {list_col}", color_discrete_sequence=['#2B7A78'])
                    st.plotly_chart(fig, use_container_width=True)
                
                elif query_info['operation'] == 'count_value':
                    agg_col = query_info.get('agg_column')
                    count_val = query_info.get('count_value')
                    fig = px.bar(result_df, x=f"count({count_val})", title=f"Count of {count_val}", color_discrete_sequence=['#2B7A78'])
                    st.plotly_chart(fig, use_container_width=True)
                
                elif query_info['operation'] == 'group_aggregate':
                    group_col = query_info.get('group_by')
                    if chart_type == 'pie_chart':
                        fig = px.pie(result_df, names=group_col, values='Count', title=f"Count by {group_col}",
                                     color_discrete_sequence=px.colors.qualitative.Plotly)
                    elif chart_type == 'donut_chart':
                        fig = px.pie(result_df, names=group_col, values='Count', title=f"Count by {group_col}", hole=0.4,
                                     color_discrete_sequence=px.colors.qualitative.Plotly)
                    elif chart_type == 'treemap':
                        fig = px.treemap(result_df, path=[group_col], values='Count', title=f"Count by {group_col}",
                                         color_discrete_sequence=px.colors.qualitative.Plotly)
                    else:
                        fig = px.bar(result_df, x=group_col, y='Count', title=f"Count by {group_col}", color_discrete_sequence=['#2B7A78'])
                    st.plotly_chart(fig, use_container_width=True)
                
                elif query_info['operation'] == 'aggregate':
                    agg_col = query_info.get('agg_column')
                    agg_func = query_info.get('agg_func')
                    fig = px.bar(result_df, x=f"{agg_func}({agg_col})", title=f"{agg_func.capitalize()} of {agg_col}",
                                 color_discrete_sequence=['#2B7A78'])
                    st.plotly_chart(fig, use_container_width=True)
                
                elif query_info['operation'] == 'group_top':
                    group_col = query_info.get('group_by')
                    sort_col = query_info.get('sort_column')
                    fig = px.bar(result_df, x='Department', y=sort_col, color='Job_Title',
                                 title=f"Top Employees by {sort_col} per Department")
                    st.plotly_chart(fig, use_container_width=True)
                
                else:
                    if chart_type == 'bar_chart' and 'Job_Title' in result_df.columns and 'Annual Salary' in result_df.columns:
                        fig = px.bar(result_df, x='Employee_ID', y='Annual Salary', color='Job_Title',
                                     title="Employees Matching Criteria by Salary")
                    elif chart_type == 'histogram' and any(col in result_df.columns for col in ['Annual Salary', 'Performance_Score', 'Overtime_Hours', 'Number_of_Projects']):
                        num_col = next(col for col in ['Annual Salary', 'Performance_Score', 'Overtime_Hours', 'Number_of_Projects'] if col in result_df.columns)
                        fig = px.histogram(result_df, x=num_col, title=f"Distribution of {num_col}",
                                           color_discrete_sequence=['#2B7A78'])
                    elif chart_type == 'scatter_plot' and len([col for col in result_df.columns if col in ['Performance_Score', 'Employee_Satisfaction_Score', 'Annual Salary', 'Years_At_Company', 'Number_of_Projects', 'Overtime_Hours']]) >= 2:
                        num_cols = [col for col in ['Performance_Score', 'Employee_Satisfaction_Score', 'Annual Salary', 'Years_At_Company', 'Number_of_Projects', 'Overtime_Hours'] if col in result_df.columns]
                        fig = px.scatter(result_df, x=num_cols[0], y=num_cols[1], color='Job_Title',
                                         title=f"{num_cols[0]} vs {num_cols[1]}")
                    else:
                        fig = px.bar(result_df, x='Employee_ID', y=result_df.columns[1], title="Employee Data",
                                     color_discrete_sequence=['#2B7A78'])
                    st.plotly_chart(fig, use_container_width=True)

# Auto-refresh every 5 minutes
st_autorefresh(interval=5 * 60 * 1000, key="data_refresh")
