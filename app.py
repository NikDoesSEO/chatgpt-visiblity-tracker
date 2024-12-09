import streamlit as st
from openai import OpenAI
import pandas as pd
from datetime import datetime
import time
import re
from statistics import mean, median
from io import BytesIO

class ChatGPTTracker:
    def __init__(self, api_key: str, brand: str, model: str = "gpt-3.5-turbo"):
        # Initialize OpenAI client with only the API key
        self.client = OpenAI(
            api_key=api_key,  # Only pass api_key
        )
        self.brand = brand.lower()
        self.model = model
    
    def generate_prompts(self, query: str):
        """Generate different prompts to test brand visibility"""
        return [
            f"List top 10 companies/websites for {query}",
            f"What are the best options for {query}?",
            f"Name the leading providers of {query}",
            f"Who are the most trusted companies for {query}?",
            f"List the market leaders in {query}"
        ]
    
    def analyze_response(self, text: str):
        """Analyze where the brand appears in the response"""
        # Split into items, handling different list formats
        items = re.split(r'\n\d+\.|\n-|\n\*|\n(?=[A-Z])', text)
        items = [item.strip() for item in items if item.strip()]
        
        position = None
        context = None
        
        # Find brand position and context
        for idx, item in enumerate(items, 1):
            if self.brand in item.lower():
                position = idx
                context = item.strip()
                break
                
        return {
            'position': position,
            'total_results': len(items),
            'context': context
        }
    
    def check_brand_visibility(self, query: str, progress_bar=None):
        """Check brand visibility across multiple prompts"""
        prompts = self.generate_prompts(query)
        results = []
        
        for idx, prompt in enumerate(prompts):
            # Update progress
            if progress_bar:
                progress_bar.progress((idx + 1) / len(prompts))
            
            try:
                # Make API call
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a search expert. Provide numbered lists of relevant results based on market presence and popularity."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7
                )
                
                # Analyze response
                answer = response.choices[0].message.content
                analysis = self.analyze_response(answer)
                
                results.append({
                    'prompt': prompt,
                    'position': analysis['position'],
                    'total_results': analysis['total_results'],
                    'context': analysis['context']
                })
                
                # Rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                st.error(f"Error: {str(e)}")
        
        return self.summarize_results(results)
    
    def summarize_results(self, results):
        """Summarize visibility results"""
        positions = [r['position'] for r in results if r['position'] is not None]
        
        return {
            'raw_results': results,
            'summary': {
                'times_mentioned': len(positions),
                'times_not_mentioned': len(results) - len(positions),
                'average_position': round(mean(positions), 2) if positions else None,
                'median_position': median(positions) if positions else None,
                'best_position': min(positions) if positions else None,
                'worst_position': max(positions) if positions else None
            }
        }

def main():
    st.title("Brand Visibility Checker")
    st.markdown("Track how often and where your brand appears in ChatGPT responses")
    
    # Sidebar inputs
    with st.sidebar:
        api_key = st.text_input("OpenAI API Key", type="password")
        brand = st.text_input("Brand/Website to track")
        query = st.text_input("Search query")
        model = st.selectbox("Model", ["gpt-3.5-turbo", "gpt-4"])
        
        analyze = st.button("Analyze Visibility")
    
    if analyze and api_key and brand and query:
        try:
            # Create tracker and progress bar
            tracker = ChatGPTTracker(api_key, brand, model)
            progress = st.progress(0)
            
            # Run analysis
            results = tracker.check_brand_visibility(query, progress)
            
            # Display results
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Summary")
                summary = results['summary']
                st.write(f"Times mentioned: {summary['times_mentioned']}/5")
                if summary['average_position']:
                    st.write(f"Average position: {summary['average_position']}")
                    st.write(f"Best position: {summary['best_position']}")
            
            with col2:
                st.subheader("Details")
                for result in results['raw_results']:
                    if result['position']:
                        st.write(f"Position {result['position']}: {result['context']}")
            
            # Export option
            if st.button("Export Results"):
                # Create Excel file
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    # Results sheet
                    pd.DataFrame(results['raw_results']).to_excel(
                        writer, sheet_name='Detailed Results', index=False
                    )
                    # Summary sheet
                    pd.DataFrame([results['summary']]).to_excel(
                        writer, sheet_name='Summary', index=False
                    )
                
                buffer.seek(0)
                st.download_button(
                    label="Download Excel Report",
                    data=buffer,
                    file_name=f"visibility_report_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.ms-excel"
                )
                
        except Exception as e:
            st.error(f"Analysis failed: {str(e)}")

if __name__ == "__main__":
    main()
