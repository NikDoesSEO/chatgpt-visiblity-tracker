import streamlit as st
import openai
from typing import List, Dict
import pandas as pd
import time
from datetime import datetime
import re

# Configure the page
st.set_page_config(
    page_title="ChatGPT Visibility and Ranking Tracker",
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
        f"What are the most popular choices for {query}? Rank them.",
        f"List the market leaders for {query}.",
        f"What are the top-rated options for {query}?",
        f"Rank the most recommended solutions for {query}.",
        f"Which providers are most trusted for {query}? List in order.",
        f"What are the best available options for {query}? Rank them.",
        f"What is the best {query}?",
        f"Which are the best {query} and why?",
        f"What's the absolute best {query} available today?",
        f"List the best {query} options from best to worst.",
        f"Who offers the best {query} service?"
    ]

def analyze_response(response_text: str, brand_name: str, competitor_brand: str) -> Dict:
    """Analyze a single response for both brands"""
    items = re.split(r'\n\d+\.|\n-|\n\*|\n(?=[A-Z])', response_text.lower())
    items = [item.strip() for item in items if item.strip()]
    
    brand_results = {}
    for brand in [brand_name, competitor_brand]:
        if brand:  # Only analyze if brand name is provided
            brand_lower = brand.lower()
            mentions = []
            positions = []
            
            for idx, item in enumerate(items, 1):
                if brand_lower in item:
                    mentions.append(item)
                    positions.append(idx)
            
            brand_results[brand] = {
                'mentions': mentions,
                'positions': positions,
                'mention_count': len(mentions)
            }
    
    return {
        'brand_results': brand_results,
        'total_items': len(items)
    }

def analyze_top_brands(results: Dict) -> Dict:
    """Analyze all responses to find top mentioned brands"""
    brand_mentions = {}
    
    for result in results['detailed_results']:
        # Split into lines and process numbered items
        lines = result['response'].split('\n')
        for line in lines:
            # Look for numbered list items
            if re.match(r'^\d+\.', line):
                # Extract the text after the number until a dash or period
                match = re.search(r'^\d+\.\s*(.*?)(?:\s*-|\.|$)', line)
                if match:
                    # Get the brand name part
                    brand = match.group(1).strip()
                    
                    # Handle cases with parentheses
                    brand = re.sub(r'\s*\([^)]*\)', '', brand)
                    
                    # Special handling for common prefixes
                    brand = re.sub(r'^(Amazon Web Services|Microsoft Azure|Google Cloud Platform)\s+', r'\1 ', brand, flags=re.IGNORECASE)
                    
                    # Clean up the brand name
                    brand = brand.strip()
                    
                    if brand and len(brand) > 1:
                        brand_mentions[brand] = brand_mentions.get(brand, 0) + 1
    
    # Sort brands by mention count
    sorted_brands = sorted(brand_mentions.items(), key=lambda x: x[1], reverse=True)
    
    return {
        'top_mentioned': sorted_brands[:3]
    }

def run_analysis(client, brand_name: str, competitor_brand: str, query: str, model: str, progress_bar) -> Dict:
    """Run the complete analysis using multiple prompts"""
    prompts = generate_prompts(query)
    results = []
    brand_totals = {brand_name: {'mentions': 0, 'positions': []} for brand in [brand_name, competitor_brand] if brand}
    if competitor_brand:
        brand_totals[competitor_brand] = {'mentions': 0, 'positions': []}
    
    for i, prompt in enumerate(prompts):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": """You are a search expert. Provide clear, numbered lists with brand/company names at the start of each item. 
                     Format each line as: '1. [Brand Name] - description'. Always start with the company/brand name followed by details.
                     Example format:
                     1. Apple - Leading technology company known for iPhone
                     2. Samsung - Major electronics manufacturer
                     Keep responses focused on actual company and brand names."""},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            
            response_text = response.choices[0].message.content
            analysis = analyze_response(response_text, brand_name, competitor_brand)
            
            results.append({
                'prompt': prompt,
                'response': response_text,
                'analysis': analysis
            })
            
            # Aggregate results for each brand
            for brand in brand_totals:
                if brand in analysis['brand_results']:
                    brand_totals[brand]['mentions'] += analysis['brand_results'][brand]['mention_count']
                    brand_totals[brand]['positions'].extend(analysis['brand_results'][brand]['positions'])
            
            # Update progress
            progress_bar.progress((i + 1) / len(prompts))
            time.sleep(0.1)  # Small delay to prevent rate limiting
            
        except Exception as e:
            st.error(f"Error in analysis: {str(e)}")
    
    # Calculate summary statistics for each brand
    summary = {}
    for brand in brand_totals:
        positions = brand_totals[brand]['positions']
        avg_position = sum(positions) / len(positions) if positions else 0
        summary[brand] = {
            'total_mentions': brand_totals[brand]['mentions'],
            'average_position': round(avg_position, 2),
            'times_ranked': len(positions),
            'rankings': positions
        }
    
    return {
        'detailed_results': results,
        'summary': summary
    }

def display_results(results: Dict):
    """Display analysis results in a structured format"""
    # Get brands from results
    brands = list(results['summary'].keys())
    
    # Create columns for each brand plus one for general stats
    cols = st.columns(len(brands))
    
    # Display metrics for each brand
    for idx, brand in enumerate(brands):
        with cols[idx]:
            st.subheader(f"{brand} Metrics")
            summary = results['summary'][brand]
            st.metric("Total Mentions", summary['total_mentions'])
            st.metric("Average Position", f"#{summary['average_position']}")
            st.metric("Times Ranked", summary['times_ranked'])
    
    # Display top brands analysis
    st.subheader("Top Mentioned Brands Overall")
    top_brands = analyze_top_brands(results)
    
    for i, (brand, count) in enumerate(top_brands['top_mentioned'], 1):
        st.write(f"{i}. {brand.title()} - {count} mentions")
    
    # Display detailed results in an expander
    with st.expander("View Detailed Results"):
        for result in results['detailed_results']:
            st.subheader(f"Prompt: {result['prompt']}")
            st.write("Response:", result['response'])
            for brand in brands:
                if brand in result['analysis']['brand_results']:
                    analysis = result['analysis']['brand_results'][brand]
                    st.write(f"{brand} Mentions: {len(analysis['mentions'])}")
                    st.write(f"{brand} Positions: {analysis['positions']}")
            st.divider()

def main():
    # Header
    st.title("🔍 ChatGPT Visibility and Ranking Tracker")
    st.markdown("Analyze how your brand appears in ChatGPT's responses. Enter your brand name and a search query to get detailed insights.")
    
    # Input section
    with st.form("analysis_form"):
        # Model selection
        model_choice = st.selectbox(
            "Select GPT Model",
            ["gpt-3.5-turbo", "gpt-4o", "gpt-4o-mini"]
        )
        
        col1, col2 = st.columns(2)
        with col1:
            brand_name = st.text_input("Your Brand Name", placeholder="e.g., Tyk")
            competitor_brand = st.text_input("Competitor Brand (Optional)", placeholder="e.g., Kong")
        with col2:
            search_query = st.text_input("Search Query", placeholder="e.g., API Gateway")
        
        submitted = st.form_submit_button("Analyze Brand Visibility")
    
    # Analysis section
    if submitted and brand_name and search_query:
        try:
            # Initialize OpenAI client
            client = initialize_openai()
            
            # Show progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            status_text.text("Running analysis...")
            
            # Run analysis with selected model
            results = run_analysis(client, brand_name, competitor_brand, search_query, model_choice, progress_bar)
            
            # Store results in session state
            st.session_state.analysis_results = results
            
            # Clear progress indicators
            progress_bar.empty()
            status_text.empty()
            
            # Display results
            display_results(results)
            
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.session_state.is_analyzing = False

if __name__ == "__main__":
    main()
