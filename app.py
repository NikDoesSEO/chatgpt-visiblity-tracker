import streamlit as st
import os
from openai import OpenAI
import pandas as pd
from datetime import datetime
import time
from typing import List, Dict
import re
from statistics import mean, median
from io import BytesIO

class WebsitePositionTracker:
    def __init__(self, api_key: str, target_website: str, model: str = "gpt-3.5-turbo"):
        self.client = OpenAI(api_key=api_key)
        self.target_website = target_website.lower()
        self.model = model
        self.results = []
        self.rate_limits = {
            "gpt-3.5-turbo": 0.02,
            "gpt-4": 0.12,
            "gpt-4o": 0.04,
            "gpt-4o-mini": 0.04,
            "gpt-4-turbo": 0.04
        }
        self.rate_limit = self.rate_limits.get(model, 0.12)

    def generate_search_prompts(self, query: str) -> List[str]:
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

    def analyze_position(self, response_text: str) -> Dict:
        items = re.split(r'\n\d+\.|\n-|\n\*|\n(?=[A-Z])', response_text)
        items = [item.strip() for item in items if item.strip()]
        
        position = None
        context = None
        
        for idx, item in enumerate(items, 1):
            if self.target_website in item.lower():
                position = idx
                context = item.strip()
                break
                
        return {
            'position': position,
            'total_mentions': len(items),
            'context': context
        }

    def perform_searches(self, query: str, num_variations: int = 15, progress_bar=None) -> Dict:
        search_prompts = self.generate_search_prompts(query)
        
        search_results = {
            'query': query,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'model': self.model,
            'searches': []
        }

        for idx, prompt in enumerate(search_prompts[:num_variations], 1):
            try:
                time.sleep(self.rate_limit)

                if progress_bar is not None:
                    progress_bar.progress(idx / num_variations)

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a search expert. Provide clear, numbered lists of relevant results based on popularity and market presence. Include brief context for each option."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500,
                    temperature=0.7
                )

                answer = response.choices[0].message.content
                position_analysis = self.analyze_position(answer)

                search_results['searches'].append({
                    'search_number': idx,
                    'prompt': prompt,
                    'position': position_analysis['position'],
                    'total_mentions': position_analysis['total_mentions'],
                    'context': position_analysis['context'],
                    'full_response': answer
                })

            except Exception as e:
                st.error(f"Error in search {idx}: {str(e)}")
                search_results['searches'].append({
                    'search_number': idx,
                    'error': str(e)
                })

        positions = [s['position'] for s in search_results['searches'] if s.get('position')]
        search_results['summary'] = {
            'times_mentioned': len(positions),
            'times_not_mentioned': num_variations - len(positions),
            'average_position': round(mean(positions), 2) if positions else None,
            'median_position': median(positions) if positions else None,
            'best_position': min(positions) if positions else None,
            'worst_position': max(positions) if positions else None,
        }

        self.results.append(search_results)
        return search_results

def main():
    st.set_page_config(page_title="ChatGPT Position Tracker", layout="wide")
    
    st.title("ChatGPT Position Tracker")
    st.markdown("Track website/brand positions in ChatGPT responses")
    
    # Sidebar for inputs
    with st.sidebar:
        st.header("Configuration")
        api_key = st.text_input("OpenAI API Key", type="password")
        
        models = {
            "GPT-4": "gpt-4",
            "GPT-4 Turbo": "gpt-4-turbo",
            "GPT-3.5 Turbo": "gpt-3.5-turbo"
        }
        
        model = st.selectbox("Select Model", list(models.keys()))
        target_website = st.text_input("Target Website/Brand")
        query = st.text_input("Search Query")
        
        start_analysis = st.button("Start Analysis")

    if start_analysis and api_key and target_website and query:
        tracker = WebsitePositionTracker(api_key, target_website, models[model])
        
        # Create progress bar
        progress_bar = st.progress(0)
        st.info("Analysis in progress...")
        
        # Run analysis
        results = tracker.perform_searches(query, progress_bar=progress_bar)
        
        # Display results
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Summary Statistics")
            st.write(f"Average Position: {results['summary']['average_position']}")
            st.write(f"Median Position: {results['summary']['median_position']}")
            st.write(f"Best Position: {results['summary']['best_position']}")
            st.write(f"Times Mentioned: {results['summary']['times_mentioned']}/15")
        
        with col2:
            st.subheader("Visualization")
            positions = [s['position'] for s in results['searches'] if s.get('position')]
            if positions:
                df = pd.DataFrame(positions, columns=['Position'])
                st.bar_chart(df['Position'].value_counts())
        
        # Detailed results in expandable section
        with st.expander("View Detailed Results"):
            for search in results['searches']:
                st.markdown(f"### Search {search['search_number']}")
                st.write(f"Position: {search.get('position')}")
                st.write(f"Context: {search.get('context')}")
                with st.expander("View Full Response"):
                    st.write(search.get('full_response'))
        
        # Export button
        if st.button("Export to Excel"):
            df_detailed = pd.DataFrame(results['searches'])
            df_summary = pd.DataFrame([results['summary']])
            
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_detailed.to_excel(writer, sheet_name='Detailed Results', index=False)
                df_summary.to_excel(writer, sheet_name='Summary', index=False)
            
            buffer.seek(0)
            st.download_button(
                label="Download Excel file",
                data=buffer,
                file_name=f"position_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.ms-excel"
            )

if __name__ == "__main__":
    main()