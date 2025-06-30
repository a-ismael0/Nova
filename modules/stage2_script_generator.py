import os
import json
import pandas as pd
from datetime import datetime
from typing import List, Optional
import openai

# Set your OpenAI API key
openai.api_key = "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"

class NovaClipScriptGenerator:
    def __init__(self, socketio=None):
        self.socketio = socketio
        self.output_dir = 'outputs/scripts'
        os.makedirs(self.output_dir, exist_ok=True)
        self.stop_processing = False
    
    def emit_log(self, message: str, log_type: str = 'info'):
        """Emit log message to frontend"""
        if self.socketio:
            self.socketio.emit('log', {'message': message, 'type': log_type})
        print(f"[{log_type.upper()}] {message}")
    
    def check_stop_signal(self):
        """Check if processing should be stopped"""
        return self.stop_processing
    
    def build_prompt(self, topic: str, video_type: str = "Who is", video_duration: str = "1 to 2 minutes") -> str:
        """Build prompt for script generation"""
        return f"""
You are a content creator specializing in sports history and storytelling for YouTube.

Create a highly engaging script and video description for a {video_duration} YouTube video titled: "{video_type} {topic}".

### Script Content Requirements:
- Structure the script in 3 parts: The Origins, The Achievements, and The Impact
- Write it for narration, suitable for a YouTube video with energetic pacing and a documentary-style tone
- The total length should be about 1 to 2 minutes, which means roughly 150 to 300 words
- Include timestamps for each section in the format (mm:ss - mm:ss), dividing the script evenly
- Each section should have a title heading in square brackets, e.g. [THE ORIGINS]

### Description Requirements:
After the script, write a YouTube video description using this structure:
- Hook (1-2 lines): Catchy intro or question
- Summary (2-3 lines): Recap the topic and what viewers will learn
- Call to Action (1-2 lines): Ask users to like, comment, or subscribe
- Relevant Hashtags

Output the script first, then the YouTube description.
"""
    
    def generate_content(self, prompt: str, model: str = "gpt-4", temperature: float = 0.8) -> Optional[str]:
        """Generate content using OpenAI"""
        if self.check_stop_signal():
            return None
            
        try:
            response = openai.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature
            )
            return response.choices[0].message.content if response.choices else None
        except Exception as e:
            self.emit_log(f"❌ Error calling OpenAI API: {e}", 'error')
            return None
    
    def save_script(self, content: str, filename: str) -> bool:
        """Save script content to file"""
        try:
            filepath = os.path.join(self.output_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            self.emit_log(f"💾 Script saved: {filename}")
            return True
        except Exception as e:
            self.emit_log(f"❌ Error saving script: {e}", 'error')
            return False
    
    def extract_visual_keywords(self, script_text: str, model: str = "gpt-4", temperature: float = 0.5) -> List[str]:
        """Extract visual keywords from script for image search"""
        if self.check_stop_signal():
            return []
            
        keyword_prompt = f"""
You're an assistant helping video editors find visual assets for YouTube videos.

Given the following narration script, extract a list of 5–8 **visual search terms** a user can input into Google Images or a stock image tool. Focus on:
- Famous locations or cities
- Notable people mentioned
- Specific events or awards
- Visual symbols related to the story
- Car or race-related terms if relevant

Return as a clean Python list of strings. Here's the script:

\"\"\"{script_text}\"\"\"
"""
        try:
            keyword_response = openai.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": keyword_prompt}],
                temperature=temperature
            )
            keyword_content = keyword_response.choices[0].message.content if keyword_response.choices else None
            
            if keyword_content:
                try:
                    # Try to parse as JSON list
                    parsed = json.loads(keyword_content.strip())
                    return parsed if isinstance(parsed, list) else []
                except json.JSONDecodeError:
                    # If not valid JSON, try to extract keywords manually
                    lines = keyword_content.strip().split('\n')
                    keywords = []
                    for line in lines:
                        line = line.strip()
                        if line and not line.startswith('#') and not line.startswith('*'):
                            # Remove quotes and list markers
                            line = line.strip('"\'- ')
                            if line:
                                keywords.append(line)
                    return keywords[:8]  # Limit to 8 keywords
            else:
                self.emit_log("⚠️ No keyword content returned from OpenAI", 'warning')
                return []
        except Exception as e:
            self.emit_log(f"❌ Error extracting keywords: {e}", 'error')
            return []
    
    def filter_valid_rows(self, input_file: str) -> pd.DataFrame:
        """Filter DataFrame for valid persons within search result range"""
        df = pd.read_excel(input_file)
        
        # Convert "Search Results" to numeric
        df["Search Results"] = pd.to_numeric(df["Search Results"], errors="coerce")
        
        # Apply filtering criteria
        self.emit_log("📊 Filtering: persons with 1M-20M search results")
        filtered_df = df[
            (df["Is Person"] == True) &
            (df["Search Results"].between(1_000_000, 20_000_000))
        ]
        
        self.emit_log(f"✅ Found {len(filtered_df)} valid entries for script generation")
        return filtered_df
    
    def generate_scripts_from_file(self, input_file: str) -> bool:
        """Generate scripts for all valid entries in the file"""
        if self.check_stop_signal():
            return False
            
        try:
            df = self.filter_valid_rows(input_file)
            
            if df.empty:
                self.emit_log("⚠️ No valid entries found for script generation", 'warning')
                return False
            
            total_entries = len(df)
            success_count = 0
            
            for idx, (_, row) in enumerate(df.iterrows(), 1):
                if self.check_stop_signal():
                    self.emit_log("⛔ Script generation stopped by user", 'warning')
                    break
                    
                topic = row['Name']
                self.emit_log(f"🎬 Generating script {idx}/{total_entries}: {topic}")
                
                # Generate script
                prompt = self.build_prompt(topic=topic, video_type="Who is", video_duration="1 to 2 minutes")
                content = self.generate_content(prompt)
                
                if self.check_stop_signal():
                    break
                
                if content:
                    # Create filename
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_filename = topic.replace(' ', '_').replace('/', '_')
                    filename = f"{safe_filename}_script_{timestamp}.txt"
                    
                    # Save script
                    if self.save_script(content, filename):
                        success_count += 1
                        
                        if not self.check_stop_signal():
                            # Extract visual keywords
                            keywords = self.extract_visual_keywords(content)
                            if keywords:
                                self.emit_log(f"🔑 Visual keywords for {topic}: {', '.join(keywords[:3])}...")
                            
                            # Save keywords to separate file
                            keywords_filename = f"{safe_filename}_keywords_{timestamp}.json"
                            keywords_filepath = os.path.join(self.output_dir, keywords_filename)
                            try:
                                with open(keywords_filepath, 'w', encoding='utf-8') as f:
                                    json.dump({
                                        'topic': topic,
                                        'keywords': keywords,
                                        'generated_at': datetime.now().isoformat()
                                    }, f, indent=2, ensure_ascii=False)
                            except Exception as e:
                                self.emit_log(f"⚠️ Could not save keywords: {e}", 'warning')
                    
                else:
                    self.emit_log(f"⚠️ Failed to generate script for {topic}", 'warning')
            
            if not self.check_stop_signal():
                self.emit_log(f"✅ Script generation completed: {success_count}/{total_entries} successful")
            
            return success_count > 0
            
        except Exception as e:
            if not self.check_stop_signal():
                self.emit_log(f"❌ Script generation failed: {e}", 'error')
            return False
    
    def generate_single_script(self, name: str) -> bool:
        """Generate a single script for a given name"""
        if self.check_stop_signal():
            return False
            
        try:
            self.emit_log(f"🎬 Generating script for: {name}")
            
            prompt = self.build_prompt(name, "Who is", "1 to 2 minutes")
            content = self.generate_content(prompt)
            
            if self.check_stop_signal():
                return False
            
            if content:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_filename = name.replace(' ', '_').replace('/', '_')
                filename = f"{safe_filename}_script_{timestamp}.txt"
                
                if self.save_script(content, filename):
                    if not self.check_stop_signal():
                        keywords = self.extract_visual_keywords(content)
                        self.emit_log(f"🔑 Visual keywords: {', '.join(keywords[:5])}")
                    return True
            
            return False
            
        except Exception as e:
            if not self.check_stop_signal():
                self.emit_log(f"❌ Single script generation failed: {e}", 'error')
            return False