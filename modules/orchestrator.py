import os
import time
import threading
from datetime import datetime
from typing import Optional
from extensions import socketio
from .stage1_scraper import NovaClipScraper
from .stage2_script_generator import NovaClipScriptGenerator
from .stage3_image_generator import NovaClipImageGenerator

class NovaClipOrchestrator:
    def __init__(self, socketio, geo_region='US', source_url=None):
        self.socketio = socketio
        self.stop_processing = False
        self.processing_lock = threading.Lock()
        self.geo_region = geo_region
        self.source_url = source_url or f'https://trends.google.com/tv/?rows=5&cols=5&geo={geo_region}'
        
        # Initialize stage processors
        self.scraper = NovaClipScraper(socketio)
        self.script_generator = NovaClipScriptGenerator(socketio)
        self.image_generator = NovaClipImageGenerator(socketio)
        
        # Progress tracking
        self.current_progress = 0
        self.total_stages = 3
        
        # Thread management
        self.processing_thread = None

    def cleanup(self):
        """Safe cleanup of all resources"""
        try:
            if hasattr(self, 'scraper') and hasattr(self.scraper, 'driver') and self.scraper.driver:
                self.scraper.driver.quit()
                self.scraper.driver = None
        except Exception as e:
            print(f"Cleanup error: {e}")
        finally:
            with self.processing_lock:
                self.stop_processing = True

    def get_latest_trends_file(self):
        """Get the most recent trends file"""
        trends_dir = 'outputs/trends_data'
        if not os.path.exists(trends_dir):
            return None
        
        files = [f for f in os.listdir(trends_dir) if f.endswith('.xlsx')]
        if not files:
            return None
        
        # Sort by modification time, newest first
        files.sort(key=lambda x: os.path.getmtime(os.path.join(trends_dir, x)), reverse=True)
        return os.path.join(trends_dir, files[0])

    def run_pipeline_threaded(self):
        """Run the entire pipeline in a separate thread"""
        self.processing_thread = threading.Thread(target=self._run_pipeline)
        self.processing_thread.start()

    def _run_pipeline(self):
        """Private method for thread execution"""
        try:
            trends_file = self.run_stage_one()
            if trends_file and not self.check_stop_signal():
                self.run_stage_two(trends_file)
                if not self.check_stop_signal():
                    self.run_stage_three(trends_file)
                    self.socketio.emit('process_complete')
        except Exception as e:
            self.socketio.emit('process_error', {'error': str(e)})

    def emit_log(self, message: str, log_type: str = 'info'):
        """Emit log message to frontend"""
        self.socketio.emit('log', {'message': message, 'type': log_type})
        print(f"[{log_type.upper()}] {message}")

    def emit_progress(self, percentage: int):
        """Emit progress update to frontend"""
        self.current_progress = percentage
        self.socketio.emit('progress', {'percentage': percentage})

    def emit_stage_update(self, stage: int, status: str, details: str = None):
        """Emit stage status update to frontend with proper validation"""
        # Validate inputs
        if not isinstance(stage, int) or stage < 1 or stage > 3:
            print(f"ERROR: Invalid stage number: {stage}")
            return
            
        valid_statuses = ['pending', 'processing', 'completed', 'error']
        if status not in valid_statuses:
            print(f"ERROR: Invalid status '{status}' for stage {stage}")
            return
        
        # Create update data
        update_data = {
            'stage': stage,
            'status': status
        }
        
        if details and details.strip():
            update_data['details'] = details.strip()
        
        # Emit the update
        print(f"EMITTING stage_update: {update_data}")
        self.socketio.emit('stage_update', update_data)

    def check_stop_signal(self):
        """Check if processing should be stopped"""
        with self.processing_lock:
            return self.stop_processing

    def run_stage_one(self) -> Optional[str]:
        """Stage 1: Run Scraper and enrich search results with frequent stop checks."""
        socketio.emit('stage_update', {'stage': 1,'status': 'processing','details': ''})
        try:
            # Initial stop check
            if self.check_stop_signal():
                self.emit_log("🛑 Process stopped before starting Stage 1", 'warning')
                self.emit_stage_update(1, 'error', 'Stopped by user')
                return None
            
            self.emit_log("🏁 Stage 1: Scraping", 'info')
            self.emit_stage_update(1, 'processing', 'Starting scraping process...')
            self.emit_progress(5)
            
            # Extract trending names
            if self.check_stop_signal():
                self.emit_log("🛑 Process stopped during GTV page load", 'warning')
                self.emit_stage_update(1, 'error', 'Stopped during page load')
                return None
            
            self.emit_log("🔄 GTV Page loaded", 'info')
            self.emit_stage_update(1, 'processing', 'Loading Google Trends TV page...')
            self.emit_progress(10)
            
            # Modified extract_and_save_trends to accept stop callback
            trends_file = self.scraper.extract_and_save_trends(
                self.geo_region,
                stop_check=lambda: self.check_stop_signal()
            )
            
            if self.check_stop_signal():
                self.emit_log("🛑 Process stopped after trends extraction", 'warning')
                self.emit_stage_update(1, 'error', 'Stopped after trends extraction')
                return None
            
            if not trends_file or not os.path.exists(trends_file):
                self.emit_log("❌ Failed to extract trends data", 'error')
                self.emit_stage_update(1, 'error', 'Failed to extract trends data')
                return None
            
            self.emit_log("🪄 Working some magic...", 'info')
            self.emit_stage_update(1, 'processing', 'Enriching data with search results...')
            self.emit_progress(15)
            
            if self.check_stop_signal():
                self.emit_log("🛑 Process stopped during enrichment", 'warning')
                self.emit_stage_update(1, 'error', 'Stopped during enrichment')
                return None
            
            # Modified enrich_search_results to accept stop callback
            self.scraper.enrich_search_results(
                trends_file,
                stop_check=lambda: self.check_stop_signal(),
                progress_callback=lambda p: self.emit_progress(15 + (18 * p))  # 15-33% for enrichment
            )
            
            if self.check_stop_signal():
                self.emit_log("🛑 Process stopped during search enrichment", 'warning')
                self.emit_stage_update(1, 'error', 'Stopped during search enrichment')
                return None
            
            if not os.path.exists(trends_file):
                self.emit_log("❌ Enriched file not found", 'error')
                self.emit_stage_update(1, 'error', 'Enriched file not found')
                return None
            
            # Get record counts for completion message
            try:
                import pandas as pd
                df = pd.read_excel(trends_file)
                total_records = len(df)
                verified_records = len(df[df.get('GPT Verified', False) == True])
                completion_details = f'Found {verified_records} verified records from {total_records} total'
            except Exception as e:
                completion_details = 'Scraping completed successfully'
            
            socketio.emit('stage_update', {'stage': 1,'status': 'completed','details': completion_details})
            self.emit_log("📦 File saved successfully!", 'success')
            self.emit_stage_update(1, 'completed', completion_details)
            self.emit_progress(33)
            
            return trends_file
        
        except Exception as e:
            if not self.check_stop_signal():
                self.emit_log(f"❌ Stage 1 failed: {str(e)}", 'error')
                self.emit_stage_update(1, 'error', f'Stage 1 failed: {str(e)}')
            return None

    def run_stage_two(self, input_file: str = None) -> bool:
        """Stage 2: Generate video scripts."""
        socketio.emit('stage_update', {'stage': 2, 'status': 'processing', 'details': 'Starting stage 2'})
        try:
            if self.check_stop_signal():
                self.emit_stage_update(2, 'error', 'Stopped by user')
                return False
            
            # Use latest file if no input file specified
            if not input_file:
                input_file = self.get_latest_trends_file()
                if not input_file:
                    self.emit_log("❌ No trends file found for script generation", 'error')
                    self.emit_stage_update(2, 'error', 'No trends file found')
                    return False
                
            self.emit_log("🏁 Kicking Stage 2: Script Generation", 'info')
            self.emit_stage_update(2, 'processing', 'Starting script generation...')
            self.emit_progress(40)
            
            if self.check_stop_signal():
                self.emit_stage_update(2, 'error', 'Stopped by user')
                return False
            
            self.emit_log("🔄 Generating Scripts", 'info')
            self.emit_stage_update(2, 'processing', 'Generating AI-powered scripts...')
            self.emit_progress(50)
            
            # Pass stop check to script generator
            self.script_generator.stop_processing = self.stop_processing
            success = self.script_generator.generate_scripts_from_file(input_file)
            
            if self.check_stop_signal():
                self.emit_stage_update(2, 'error', 'Stopped by user')
                return False
            
            if success:
                # Get script count for completion message
                try:
                    scripts_dir = 'outputs/scripts'
                    script_count = len([f for f in os.listdir(scripts_dir) if f.endswith('.txt')])
                    completion_details = f'Generated {script_count} scripts'
                except Exception:
                    completion_details = 'Script generation completed'
                
                self.emit_log("📦 Scripts saved successfully!", 'success')
                self.emit_stage_update(2, 'completed', completion_details)
                self.emit_progress(66)
                return True
            else:
                self.emit_log("❌ Stage 2 failed", 'error')
                self.emit_stage_update(2, 'error', 'Script generation failed')
                return False
                
        except Exception as e:
            if not self.check_stop_signal():
                self.emit_log(f"❌ Stage 2 failed: {str(e)}", 'error')
                self.emit_stage_update(2, 'error', f'Stage 2 failed: {str(e)}')
            return False

    def run_stage_three(self, input_file: str = None) -> bool:
        """Stage 3: Generate images for valid names."""
        try:
            if self.check_stop_signal():
                self.emit_stage_update(3, 'error', 'Stopped by user')
                return False
            
            # Use latest file if no input file specified
            if not input_file:
                input_file = self.get_latest_trends_file()
                if not input_file:
                    self.emit_log("❌ No trends file found for image generation", 'error')
                    self.emit_stage_update(3, 'error', 'No trends file found')
                    return False
                
            self.emit_log("🏁 Kicking Stage 3: Image Generation", 'info')
            self.emit_stage_update(3, 'processing', 'Starting image generation...')
            self.emit_progress(70)
            
            if self.check_stop_signal():
                self.emit_stage_update(3, 'error', 'Stopped by user')
                return False
            
            self.emit_log("🔄 Generating images", 'info')
            self.emit_stage_update(3, 'processing', 'Collecting images from Google...')
            self.emit_progress(80)
            
            # Pass stop check to image generator
            self.image_generator.stop_processing = self.stop_processing
            success = self.image_generator.generate_images_from_file(input_file)
            
            if self.check_stop_signal():
                self.emit_stage_update(3, 'error', 'Stopped by user')
                return False
            
            if success:
                # Get image count for completion message
                try:
                    images_dir = 'outputs/images'
                    image_count = sum([len(files) for _, _, files in os.walk(images_dir)])
                    completion_details = f'Downloaded {image_count} images'
                except Exception:
                    completion_details = 'Image generation completed'
                
                self.emit_log("📦 Images saved successfully!", 'success')
                self.emit_stage_update(3, 'completed', completion_details)
                self.emit_progress(100)
                return True
            else:
                self.emit_log("❌ Stage 3 failed", 'error')
                self.emit_stage_update(3, 'error', 'Image generation failed')
                return False
                
        except Exception as e:
            if not self.check_stop_signal():
                self.emit_log(f"❌ Stage 3 failed: {str(e)}", 'error')
                self.emit_stage_update(3, 'error', f'Stage 3 failed: {str(e)}')
            return False