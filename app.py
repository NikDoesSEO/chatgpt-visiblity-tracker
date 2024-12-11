import streamlit as st
import openai
from typing import List, Dict
import pandas as pd
import time
from datetime import datetime
import re

# Configure the page
st.set_page_config(
    page_title="Brand Visibility Analyzer",
    page_icon="🔍",
    layout="wide"
)

# Initialize session state variables if they don't exist
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None
if 'is_analyzing' not in st.session_state:
    st.session_state.is_analyzing = False

def initialize_openai():
    """Initialize OpenAI client with API key"""
    api_key = st.secrets["OPENAI_API_KEY"]
    return openai.OpenAI(api_key=api_key)

def generate_prompts(query: str) -> List[str]:
    """Generate a list of prompts for analysis"""
    return [
        f"List the top 10 results for {query}.",
        f"What are the leading options for {query}? List them in order.",
        f"Rank the best solutions for {query}.",
        f"Which companies or websites are most relevant for {query}? List in order.",
        f"What are the most popular choices for {query}? Rank them."
    ]

def analyze_response(response_text: str, brand_name: str) -> Dict:
    """Analyze a single response for brand mentions and position"""
    items = re.split(r'\n\d+\.|\n-|\n\*|\n(?=[A-Z])', response_text.lower())
    items = [item.strip() for item in items if item.strip()]
    
    brand_name = brand_name.lower()
    mentions = []
    positions = []
    
    for idx, item in enumerate(items, 1):
        if brand_name in item:
            mentions.append(item)
            positions.append(idx)
    
    return {
        'mentions': mentions,
        'positions': positions,
        'total_items': len(items),
        'mention_count': len(mentions)
    }

async def run_analysis(client, brand_name: str, query: str, progress_bar) -> Dict:
    """Run the complete analysis using multiple prompts"""
    prompts = generate_prompts(query)
    results = []
    total_mentions = 0
    all_positions = []
    
    for i, prompt in enumerate(prompts):
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a search expert. Provide clear, numbered lists of relevant results."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            
            response_text = response.choices[0].message.content
            analysis = analyze_response(response_text, brand_name)
            
            results.append({
                'prompt': prompt,
                'response': response_text,
                'analysis': analysis
            })
            
            total_mentions += analysis['mention_count']
            all_positions.extend(analysis['positions'])
            
            # Update progress
            progress_bar.progress((i + 1) / len(prompts))
            
        except Exception as e:
            st.error(f"Error in analysis: {str(e)}")
    
    # Calculate summary statistics
    avg_position = sum(all_positions) / len(all_positions) if all_positions else 0
    mention_density = total_mentions / len(prompts)
    
    return {
        'detailed_results': results,
        'summary': {
            'total_mentions': total_mentions,
            'average_position': round(avg_position, 2),
            'mention_density': round(mention_density * 100, 2),
            'times_ranked': len(all_positions),
            'rankings': all_positions
        }
    }

def display_results(results: Dict):
    """Display analysis results in a structured format"""
    summary = results['summary']
    
    # Display summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Mentions", summary['total_mentions'])
    with col2:
        st.metric("Average Position", f"#{summary['average_position']}")
    with col3:
        st.metric("Mention Density", f"{summary['mention_density']}%")
    
    # Display detailed results in an expander
    with st.expander("View Detailed Results"):
        for result in results['detailed_results']:
            st.subheader(f"Prompt: {result['prompt']}")
            st.write("Response:", result['response'])
            st.write("Mentions:", len(result['analysis']['mentions']))
            st.write("Positions:", result['analysis']['positions'])
            st.divider()

def main():
    # Header
    st.title("🔍 Brand Visibility Analyzer")
    st.markdown("Analyze how your brand appears in ChatGPT's responses. Enter your brand name and a search query to get detailed insights.")
    
    # Input section
    with st.form("analysis_form"):
        col1, col2 = st.columns(2)
        with col1:
            brand_name = st.text_input("Brand Name", placeholder="e.g., Apple")
        with col2:
            search_query = st.text_input("Search Query", placeholder="e.g., smartphone")
        
        submitted = st.form_submit_button("Analyze Brand Visibility")
    
    if submitted and brand_name and search_query:
        st.session_state.is_analyzing = True
        
        # Initialize progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Initialize OpenAI client
            client = initialize_openai()
            
            # Run analysis
            status_text.text("Running analysis...")
            results = run_analysis(client, brand_name, search_query, progress_bar)
            
            # Store results in session state
            st.session_state.analysis_results = results
            st.session_state.is_analyzing = False
            
            # Clear progress indicators
            progress_bar.empty()
            status_text.empty()
            
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.session_state.is_analyzing = False
    
    # Display results if available
    if st.session_state.analysis_results is not None:
        display_results(st.session_state.analysis_results)

if __name__ == "__main__":
    main()
