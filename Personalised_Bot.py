import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from fuzzywuzzy import fuzz, process
import os
import numpy as np
import plotly.express as px
import logging
import time

logging.basicConfig(level=logging.INFO)

CACHE_FILE = 'sheet_cache.pkl'

COLUMN_ALIASES = {
    'sallary': 'Salary',
    'perfomance': 'Performance Score',
    'satisfcation': 'Satisfaction Score',
    'dept': 'Department',
    'employeeid': 'Employee ID',
    'id': 'Employee ID'
}

def load_google_sheet(sheet_url, retries=3):
    start_time = time.time()
    if os.path.exists(CACHE_FILE):
        logging.info("Loading cached data...")
        with open(CACHE_FILE, 'rb') as f:
            df = pd.read_pickle(f)
        logging.info(f"Loaded cached data in {time.time() - start_time:.2f} seconds")
        return df
    for attempt in range(retries):
        try:
            scope = ['https://www.googleapis.com/auth/spreadsheets']
            creds_path = os.getenv('GOOGLE_CREDENTIALS_PATH', 'chatbotsheetaccess-464905-cbbebbb4bf42.json')
            creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
            client = gspread.authorize(creds)
            sheet = client.open_by_url(sheet_url).sheet1
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            df = df.dropna(axis=1, how='all')
            with open(CACHE_FILE, 'wb') as f:
                pd.to_pickle(df, f)
            logging.info(f"Loaded and cached Google Sheet in {time.time() - start_time:.2f} seconds")
            return df
        except Exception as e:
            if "429" in str(e) and attempt < retries - 1:
                logging.warning(f"Rate limit hit, retrying in {2 ** attempt} seconds...")
                time.sleep(2 ** attempt)
            else:
                logging.error(f"Error loading Google Sheet: {e}")
                return None
    return None

def assign_performance_level(scores):
    scores = pd.to_numeric(scores, errors='coerce')
    return np.select([scores > 75, scores >= 50, scores < 50], ['High', 'Medium', 'Low'], default='Unknown')

def assign_satisfaction_level(scores):
    scores = pd.to_numeric(scores, errors='coerce')
    return np.select([scores > 4, scores >= 3, scores < 3], ['High', 'Medium', 'Low'], default='Unknown')

def assign_retention_risk(perf_scores, sat_scores):
    perf_scores = pd.to_numeric(perf_scores, errors='coerce')
    sat_scores = pd.to_numeric(sat_scores, errors='coerce')
    return np.select([(perf_scores > 75) & (sat_scores > 4), (perf_scores < 50) | (sat_scores < 3)], ['Low', 'High'], default='Medium')

def find_best_column(question, columns):
    question = question.lower()
    for alias, actual in COLUMN_ALIASES.items():
        if alias in question and actual in columns:
            return actual, 100
    best_match, score = process.extractOne(question, columns, scorer=fuzz.token_sort_ratio)
    return best_match, score if score >= 50 else 0

def generate_visualization(result, intent, group_by=None, agg_col=None, agg_type=None):
    try:
        if intent == 'aggregate' and not result.empty:
            if agg_type == 'count' and group_by:
                fig = px.pie(result, names=group_by, values='Count', title=f'Employee Count by {group_by.capitalize()}')
                return fig
            elif agg_type in ['mean', 'sum'] and group_by and agg_col:
                fig = px.bar(result, x=group_by, y=agg_col, title=f'{agg_type.capitalize()} {agg_col.capitalize()} by {group_by.capitalize()}')
                return fig
        return None
    except Exception as e:
        logging.error(f"Error generating visualization: {e}")
        return None

def process_question(question):
    start_time = time.time()
    if not isinstance(df, pd.DataFrame) or df.empty:
        return "Error: No data loaded from Google Sheet. Please ensure the sheet is accessible."

    question = question.lower().strip()
    columns = df.columns.str.lower().tolist()

    if 'columns' in question and 'google sheet' in question:
        result = pd.DataFrame({'Columns': df.columns.tolist()})
        logging.info(f"Processed column query in {time.time() - start_time:.2f} seconds")
        return result.to_markdown(index=False)

    keywords = []
    fuzzy_matches = []
    for word in question.split():
        matched_col, score = find_best_column(word, columns)
        if matched_col and score >= 50:
            keywords.append(matched_col)
            if score < 90:
                fuzzy_matches.append(f"Interpreting '{word}' as '{matched_col}' (similarity: {score}%)")

    if not keywords and 'columns' not in question:
        return f"No matching columns found. Available columns: {', '.join(df.columns)}"

    emp_id_match = re.search(r'\b\d+\b', question)
    emp_id = int(emp_id_match.group()) if emp_id_match else None

    visualize = any(keyword in question for keyword in ['show', 'plot', 'graph', 'chart'])

    if any(word in question for word in ['who', 'name']):
        intent = 'retrieve_name'
    elif any(word in question for word in ['average', 'sum', 'total', 'count']):
        intent = 'aggregate'
    else:
        intent = 'retrieve'

    try:
        if intent == 'retrieve_name':
            if emp_id:
                result = df[df['Employee ID'] == emp_id][['Name']]
            else:
                keyword = next((k for k in keywords if k != 'name'), 'department')
                search_term = question.split()[-1]
                result = df[df[keyword].str.contains(search_term, case=False, na=False)][['Name']]

        elif intent == 'aggregate':
            agg_type = 'mean' if 'average' in question else 'sum' if 'sum' in question else 'count'
            group_by = next((col for col in keywords if col not in df.select_dtypes(include=['int64', 'float64']).columns), None)
            if group_by:
                if agg_type == 'count':
                    result = df.groupby(group_by).size().reset_index(name='Count')
                else:
                    agg_col = next((col for col in keywords if col in df.select_dtypes(include=['int64', 'float64']).columns), None)
                    if agg_col:
                        result = df.groupby(group_by)[agg_col].agg(agg_type).reset_index()
                    else:
                        result = pd.DataFrame()
            else:
                agg_col = next((col for col in keywords if col in df.select_dtypes(include=['int64', 'float64']).columns), None)
                if agg_col:
                    result = pd.DataFrame({agg_col: [df[agg_col].agg(agg_type)]})
                else:
                    result = pd.DataFrame()

        else:
            if emp_id:
                result = df[df['Employee ID'] == emp_id][keywords]
            else:
                keyword = keywords[0] if keywords else 'department'
                search_term = question.split()[-1]
                result = df[df[keyword].str.contains(search_term, case=False, na=False)][keywords]

        visual_message = None
        if visualize and intent in ['aggregate'] and not result.empty:
            fig = generate_visualization(result, intent, group_by, agg_col if intent == 'aggregate' else None, agg_type if intent == 'aggregate' else None)
            visual_message = "Visualization generated (use fig.show() in Jupyter or save manually)" if fig else "Failed to generate visualization"

        table = result.to_markdown(index=False) if not result.empty else "No data found for the query."

        response = table
        if fuzzy_matches:
            response = f"{' '.join(fuzzy_matches)}\n\n" + response
        if visual_message:
            response += f"\n\nVisualization: {visual_message}"

        logging.info(f"Processed query in {time.time() - start_time:.2f} seconds")
        return response

    except Exception as e:
        logging.error(f"Error processing query: {e}")
        return f"Error processing query: {e}\nAvailable columns: {', '.join(df.columns)}"

sheet_url = 'https://docs.google.com/spreadsheets/d/1OxU_4C8zAp_3sqcmj2dnn4YB7N6xcI6PUPLWSG-yl4E/edit?usp=sharing'
df = load_google_sheet(sheet_url)

if df is None or df.empty:
    logging.error("Failed to load data. Using empty DataFrame.")
    df = pd.DataFrame()

if 'Performance Score' in df.columns:
    df['Performance Level'] = assign_performance_level(df['Performance Score'])
if 'Satisfaction Score' in df.columns:
    df['Satisfaction Level'] = assign_satisfaction_level(df['Satisfaction Score'])
if 'Performance Score' in df.columns and 'Satisfaction Score' in df.columns:
    df['Retention Risk Level'] = assign_retention_risk(df['Performance Score'], df['Satisfaction Score'])

def chatbot():
    print("Welcome to the Employee Data Chatbot! Ask about employee details, aggregations, or columns.")
    print("Use keywords like 'plot' or 'chart' for visualizations. Type 'exit' to quit.")
    while True:
        question = input("Your question: ")
        if question.lower() == 'exit':
            break
        response = process_question(question)
        print("\n" + response + "\n")

if __name__ == "__main__":
    chatbot()
