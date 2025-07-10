#!/usr/bin/env python3
"""
SEO Content Generator Background Agent

A background service that autonomously processes keywords and generates SEO content.
Features:
- Configurable scheduling
- Queue management
- Comprehensive logging
- Error handling and retries
- Status monitoring
- Email notifications
"""

import json
import logging
import os
import time
import yaml
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
import threading
import signal
from queue import Queue, Empty
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from seo_content_generator import SEOContentGenerator


@dataclass
class AgentConfig:
    """Configuration for the background agent"""
    # Paths
    csv_file_path: str = "kw.csv"
    output_dir: str = "generated_content"
    log_dir: str = "logs"
    config_file: str = "agent_config.yaml"

    # Sitemap
    sitemap_url: str = "https://f7i.ai/sitemap.xml"

    # Processing settings
    max_keywords_per_run: int = 5
    concurrent_workers: int = 2
    retry_attempts: int = 3
    retry_delay: int = 60  # seconds

    # Scheduling
    run_interval_hours: int = 24
    run_at_hour: int = 2  # 2 AM

    # Rate limiting
    rate_limit_delay: int = 5  # seconds between API calls

    # Notifications
    email_notifications: bool = False
    smtp_server: str = ""
    smtp_port: int = 587
    email_user: str = ""
    email_password: str = ""
    notification_recipients: Optional[List[str]] = None

    # API Keys (loaded from environment)
    gemini_api_key: str = ""
    openai_api_key: str = ""


@dataclass
class ProcessingResult:
    """Result of processing a single keyword"""
    keyword: str
    success: bool
    error_message: Optional[str] = None
    files_created: Optional[List[str]] = None
    processing_time: float = 0.0
    timestamp: Optional[datetime] = None


@dataclass
class AgentStatus:
    """Current status of the background agent"""
    is_running: bool = False
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    total_keywords_processed: int = 0
    successful_generations: int = 0
    failed_generations: int = 0
    current_queue_size: int = 0
    uptime_start: Optional[datetime] = None


class BackgroundAgent:
    """Background agent for SEO content generation"""

    def __init__(self, config_path: str = "agent_config.yaml"):
        self.config_path = config_path
        self.config = self.load_config()
        self.status = AgentStatus(uptime_start=datetime.now())

        # Setup logging
        self.setup_logging()

        # Initialize components
        self.generator = SEOContentGenerator()
        self.keyword_queue: Queue[Dict[str, Any]] = Queue()
        self.results_queue: Queue[ProcessingResult] = Queue()
        self.executor = ThreadPoolExecutor(
            max_workers=self.config.concurrent_workers)

        # Control flags
        self.shutdown_flag = threading.Event()
        self.pause_flag = threading.Event()

        # Load existing keywords and setup monitoring
        self.existing_content: List[str] = []

        self.logger.info("Background Agent initialized")

    def load_config(self) -> AgentConfig:
        """Load configuration from YAML file or create default"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config_data = yaml.safe_load(f)
                config = AgentConfig(**config_data)
                return config
            except Exception as e:
                print(f"Error loading config, using defaults: {e}")

        # Create default config
        config = AgentConfig()
        config.gemini_api_key = os.getenv('GEMINI_API_KEY', '')
        config.openai_api_key = os.getenv('OPENAI_API_KEY', '')

        # Save default config
        self.save_config(config)
        return config

    def save_config(self, config: AgentConfig):
        """Save configuration to YAML file"""
        try:
            with open(self.config_path, 'w') as f:
                yaml.dump(asdict(config), f, default_flow_style=False)
        except Exception as e:
            print(f"Error saving config: {e}")

    def setup_logging(self):
        """Setup comprehensive logging"""
        os.makedirs(self.config.log_dir, exist_ok=True)

        # Create logger
        self.logger = logging.getLogger('seo_agent')
        self.logger.setLevel(logging.INFO)

        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # File handler for detailed logs
        log_file = os.path.join(
            self.config.log_dir, f'agent_{datetime.now().strftime("%Y%m%d")}.log')
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(detailed_formatter)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(detailed_formatter)

        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def send_notification(self, subject: str, message: str):
        """Send email notification if configured"""
        if not self.config.email_notifications or not self.config.notification_recipients:
            return

        try:
            msg = MIMEMultipart()
            msg['From'] = self.config.email_user
            msg['To'] = ', '.join(self.config.notification_recipients)
            msg['Subject'] = f"SEO Agent: {subject}"

            msg.attach(MIMEText(message, 'plain'))

            server = smtplib.SMTP(self.config.smtp_server,
                                  self.config.smtp_port)
            server.starttls()
            server.login(self.config.email_user, self.config.email_password)
            server.send_message(msg)
            server.quit()

            self.logger.info(f"Notification sent: {subject}")
        except Exception as e:
            self.logger.error(f"Failed to send notification: {e}")

    def load_keywords_to_queue(self) -> int:
        """Load keywords from CSV and add to processing queue"""
        try:
            self.logger.info(
                f"Loading keywords from {self.config.csv_file_path}")

            # Load keyword data
            keyword_data = self.generator.load_keywords_from_csv(
                self.config.csv_file_path)
            if not keyword_data:
                self.logger.error("No keywords found in CSV")
                return 0

            # Load existing content
            self.existing_content = self.generator.load_existing_content_from_sitemap(
                self.config.sitemap_url
            )

            # Filter keywords
            filtered_keywords: List[str] = []
            for keyword in keyword_data.keys():
                # Check if already generated
                if self.generator.check_existing_content(keyword, self.config.output_dir):
                    continue

                # Check for overlap with existing content
                if self.generator.check_keyword_overlap(keyword, self.existing_content):
                    continue

                filtered_keywords.append(keyword)

            # Limit number of keywords per run
            keywords_to_process = filtered_keywords[:
                                                    self.config.max_keywords_per_run]

            # Add to queue
            for keyword in keywords_to_process:
                self.keyword_queue.put({
                    'keyword': keyword,
                    'serp_data': keyword_data.get(keyword, []),
                    'attempts': 0
                })

            self.logger.info(
                f"Added {len(keywords_to_process)} keywords to processing queue")
            return len(keywords_to_process)

        except Exception as e:
            self.logger.error(f"Error loading keywords: {e}")
            return 0

    def process_keyword(self, keyword_data: Dict[str, Any]) -> ProcessingResult:
        """Process a single keyword"""
        keyword = keyword_data['keyword']
        serp_data = keyword_data['serp_data']
        start_time = time.time()

        self.logger.info(f"Processing keyword: {keyword}")

        try:
            # Research keyword
            research_data = self.generator.research_keyword_with_gemini(
                keyword, serp_data)

            # Rate limiting
            time.sleep(self.config.rate_limit_delay)

            # Generate content
            blog_post = self.generator.generate_content_with_gemini(
                keyword, research_data)
            if not blog_post:
                raise Exception("Content generation failed")

            # Generate image
            image_url, local_image_path = self.generator.generate_image_with_openai(
                blog_post.image_prompt, keyword)
            blog_post.image_url = image_url
            blog_post.local_image_path = local_image_path

            # Rate limiting
            time.sleep(self.config.rate_limit_delay)

            # Format and save
            prismic_data = self.generator.format_for_prismic(blog_post)
            json_file, md_file = self.generator.save_output(
                prismic_data, keyword, blog_post.body, self.config.output_dir
            )

            processing_time = time.time() - start_time

            result = ProcessingResult(
                keyword=keyword,
                success=True,
                files_created=[json_file, md_file],
                processing_time=processing_time,
                timestamp=datetime.now()
            )

            self.logger.info(
                f"Successfully processed '{keyword}' in {processing_time:.2f}s")
            return result

        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = str(e)

            result = ProcessingResult(
                keyword=keyword,
                success=False,
                error_message=error_msg,
                processing_time=processing_time,
                timestamp=datetime.now()
            )

            self.logger.error(f"Failed to process '{keyword}': {error_msg}")
            return result

    def worker_thread(self):
        """Worker thread for processing keywords"""
        while not self.shutdown_flag.is_set():
            try:
                # Check if paused
                if self.pause_flag.is_set():
                    time.sleep(1)
                    continue

                # Get keyword from queue
                try:
                    keyword_data = self.keyword_queue.get(timeout=1)
                except Empty:
                    continue

                # Process the keyword
                result = self.process_keyword(keyword_data)

                # Handle result
                if result.success:
                    self.status.successful_generations += 1
                else:
                    self.status.failed_generations += 1

                    # Retry logic
                    keyword_data['attempts'] += 1
                    if keyword_data['attempts'] < self.config.retry_attempts:
                        self.logger.info(
                            f"Retrying {result.keyword} (attempt {keyword_data['attempts'] + 1})")
                        time.sleep(self.config.retry_delay)
                        self.keyword_queue.put(keyword_data)

                self.status.total_keywords_processed += 1
                self.results_queue.put(result)
                self.keyword_queue.task_done()

            except Exception as e:
                self.logger.error(f"Worker thread error: {e}")

    def calculate_next_run(self) -> datetime:
        """Calculate next scheduled run time"""
        now = datetime.now()
        next_run = now.replace(hour=self.config.run_at_hour,
                               minute=0, second=0, microsecond=0)

        # If we've passed today's run time, schedule for tomorrow
        if next_run <= now:
            next_run += timedelta(days=1)

        return next_run

    def run_processing_cycle(self):
        """Run a complete processing cycle"""
        self.logger.info("Starting processing cycle")
        self.status.is_running = True
        self.status.last_run = datetime.now()

        try:
            # Load keywords
            keywords_loaded = self.load_keywords_to_queue()
            if keywords_loaded == 0:
                self.logger.info("No keywords to process")
                return

            self.status.current_queue_size = keywords_loaded

            # Start worker threads
            workers = []
            for _ in range(self.config.concurrent_workers):
                worker = threading.Thread(
                    target=self.worker_thread, daemon=True)
                worker.start()
                workers.append(worker)

            # Wait for all keywords to be processed
            self.keyword_queue.join()

            # Collect results
            results: List[ProcessingResult] = []
            while not self.results_queue.empty():
                try:
                    result = self.results_queue.get(timeout=1)
                    results.append(result)
                except Empty:
                    break

            # Generate summary
            successful = sum(1 for r in results if r.success)
            failed = len(results) - successful

            summary = f"""
            Processing Cycle Complete
            ========================
            Total Keywords: {len(results)}
            Successful: {successful}
            Failed: {failed}
            Success Rate: {(successful/len(results)*100):.1f}% if results else 0.0%
            
            Successful Keywords:
            {chr(10).join([f"  - {r.keyword}" for r in results if r.success])}
            
            Failed Keywords:
            {chr(10).join([f"  - {r.keyword}: {r.error_message}" for r in results if not r.success])}
            """

            self.logger.info(summary)

            # Send notification
            if self.config.email_notifications:
                self.send_notification("Processing Cycle Complete", summary)

        except Exception as e:
            error_msg = f"Error in processing cycle: {e}"
            self.logger.error(error_msg)
            self.send_notification("Processing Cycle Error", error_msg)

        finally:
            self.status.is_running = False
            self.status.current_queue_size = 0
            self.status.next_run = self.calculate_next_run()
            self.logger.info(f"Next run scheduled for: {self.status.next_run}")

    def start(self):
        """Start the background agent"""
        self.logger.info("Starting SEO Content Generator Background Agent")

        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        self.status.next_run = self.calculate_next_run()

        # Send startup notification
        startup_msg = f"""
        SEO Content Generator Agent Started
        ==================================
        Configuration:
        - Output Directory: {self.config.output_dir}
        - CSV File: {self.config.csv_file_path}
        - Max Keywords per Run: {self.config.max_keywords_per_run}
        - Run Interval: {self.config.run_interval_hours} hours
        - Next Run: {self.status.next_run}
        """

        self.logger.info(startup_msg)
        self.send_notification("Agent Started", startup_msg)

        # Main loop
        try:
            while not self.shutdown_flag.is_set():
                now = datetime.now()

                # Check if it's time to run
                if now >= self.status.next_run and not self.status.is_running:
                    self.run_processing_cycle()

                # Sleep for 60 seconds before checking again
                time.sleep(60)

        except KeyboardInterrupt:
            self.logger.info("Shutdown requested by user")
        except Exception as e:
            self.logger.error(f"Unexpected error in main loop: {e}")
        finally:
            self.shutdown()

    def pause(self):
        """Pause processing"""
        self.pause_flag.set()
        self.logger.info("Agent paused")

    def resume(self):
        """Resume processing"""
        self.pause_flag.clear()
        self.logger.info("Agent resumed")

    def signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.shutdown_flag.set()

    def shutdown(self):
        """Graceful shutdown"""
        self.logger.info("Shutting down background agent...")
        self.shutdown_flag.set()

        # Wait for current processing to complete
        if self.status.is_running:
            self.logger.info("Waiting for current processing to complete...")
            timeout = 300  # 5 minutes
            start_time = time.time()
            while self.status.is_running and (time.time() - start_time) < timeout:
                time.sleep(1)

        # Shutdown executor
        self.executor.shutdown(wait=True)

        # Send shutdown notification
        shutdown_msg = f"""
        SEO Content Generator Agent Shutdown
        ===================================
        Uptime: {datetime.now() - (self.status.uptime_start or datetime.now())}
        Total Keywords Processed: {self.status.total_keywords_processed}
        Successful Generations: {self.status.successful_generations}
        Failed Generations: {self.status.failed_generations}
        """

        self.logger.info(shutdown_msg)
        self.send_notification("Agent Shutdown", shutdown_msg)

    def get_status(self) -> Dict[str, Any]:
        """Get current agent status"""
        return {
            'is_running': self.status.is_running,
            'last_run': self.status.last_run.isoformat() if self.status.last_run else None,
            'next_run': self.status.next_run.isoformat() if self.status.next_run else None,
            'total_keywords_processed': self.status.total_keywords_processed,
            'successful_generations': self.status.successful_generations,
            'failed_generations': self.status.failed_generations,
            'current_queue_size': self.status.current_queue_size,
            'uptime': str(datetime.now() - (self.status.uptime_start or datetime.now())),
            'config': asdict(self.config)
        }


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='SEO Content Generator Background Agent')
    parser.add_argument('--config', default='agent_config.yaml',
                        help='Configuration file path')
    parser.add_argument('--status', action='store_true',
                        help='Show current status and exit')
    parser.add_argument('--run-once', action='store_true',
                        help='Run one processing cycle and exit')

    args = parser.parse_args()

    agent = BackgroundAgent(args.config)

    if args.status:
        status = agent.get_status()
        print(json.dumps(status, indent=2))
        return

    if args.run_once:
        agent.run_processing_cycle()
        return

    # Start the agent
    agent.start()


if __name__ == "__main__":
    main()
