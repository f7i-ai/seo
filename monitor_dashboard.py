#!/usr/bin/env python3
"""
SEO Content Generator Background Agent Monitor Dashboard

A simple monitoring dashboard to view agent status, logs, and manage the service.
"""

import os
import json
import time
import subprocess
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml


class AgentMonitor:
    """Monitor for the SEO Content Generator Background Agent"""

    def __init__(self, config_path: str = "agent_config.yaml"):
        self.config_path = config_path
        self.config = self.load_config()

    def load_config(self) -> Dict[str, Any]:
        """Load agent configuration"""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return {}

    def get_agent_status(self) -> Dict[str, Any]:
        """Get current agent status by running the background agent with --status flag"""
        try:
            result = subprocess.run(
                ['python3', 'background_agent.py', '--status'],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                return {"error": f"Agent status command failed: {result.stderr}"}
        except subprocess.TimeoutExpired:
            return {"error": "Agent status command timed out"}
        except Exception as e:
            return {"error": f"Error getting agent status: {e}"}

    def get_recent_logs(self, lines: int = 50) -> List[str]:
        """Get recent log entries"""
        log_dir = self.config.get('log_dir', 'logs')
        today = datetime.now().strftime("%Y%m%d")
        log_file = os.path.join(log_dir, f"agent_{today}.log")

        if not os.path.exists(log_file):
            return ["No log file found for today"]

        try:
            result = subprocess.run(
                ['tail', '-n', str(lines), log_file],
                capture_output=True,
                text=True
            )
            return result.stdout.split('\n') if result.returncode == 0 else ["Error reading log file"]
        except Exception as e:
            return [f"Error reading logs: {e}"]

    def get_generated_content_stats(self) -> Dict[str, Any]:
        """Get statistics about generated content"""
        output_dir = self.config.get('output_dir', 'generated_content')

        if not os.path.exists(output_dir):
            return {"error": "Output directory not found"}

        json_files = list(Path(output_dir).glob("*.json"))
        md_files = list(Path(output_dir).glob("*.md"))

        # Get recent files (last 7 days)
        week_ago = datetime.now() - timedelta(days=7)
        recent_files = []

        for file_path in json_files:
            try:
                file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_time > week_ago:
                    recent_files.append({
                        'filename': file_path.name,
                        'created': file_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'size_kb': round(file_path.stat().st_size / 1024, 2)
                    })
            except Exception:
                continue

        recent_files.sort(key=lambda x: x['created'], reverse=True)

        return {
            'total_json_files': len(json_files),
            'total_md_files': len(md_files),
            'recent_files': recent_files[:10]  # Last 10 files
        }

    def get_system_info(self) -> Dict[str, Any]:
        """Get system information"""
        try:
            # Disk usage
            output_dir = self.config.get('output_dir', 'generated_content')
            disk_usage = subprocess.run(
                ['du', '-sh', output_dir],
                capture_output=True,
                text=True
            )
            disk_used = disk_usage.stdout.split(
                '\t')[0] if disk_usage.returncode == 0 else "Unknown"

            # Check if agent process is running
            ps_result = subprocess.run(
                ['pgrep', '-f', 'background_agent.py'],
                capture_output=True,
                text=True
            )
            is_process_running = ps_result.returncode == 0 and ps_result.stdout.strip()

            return {
                'disk_usage': disk_used,
                'process_running': is_process_running,
                'process_ids': ps_result.stdout.strip().split('\n') if is_process_running else []
            }
        except Exception as e:
            return {"error": f"Error getting system info: {e}"}

    def display_dashboard(self):
        """Display the monitoring dashboard"""
        print("🤖 SEO Content Generator Background Agent Monitor")
        print("=" * 60)
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        # Agent Status
        print("🔍 AGENT STATUS")
        print("-" * 20)
        status = self.get_agent_status()

        if "error" in status:
            print(f"❌ Error: {status['error']}")
        else:
            print(f"🏃 Running: {'Yes' if status.get('is_running') else 'No'}")
            print(f"⏰ Last Run: {status.get('last_run', 'Never')}")
            print(f"⏭️  Next Run: {status.get('next_run', 'Not scheduled')}")
            print(
                f"📊 Total Processed: {status.get('total_keywords_processed', 0)}")
            print(f"✅ Successful: {status.get('successful_generations', 0)}")
            print(f"❌ Failed: {status.get('failed_generations', 0)}")
            print(f"📋 Queue Size: {status.get('current_queue_size', 0)}")
            print(f"⏱️  Uptime: {status.get('uptime', 'Unknown')}")

        print()

        # System Information
        print("💻 SYSTEM INFO")
        print("-" * 20)
        system_info = self.get_system_info()

        if "error" in system_info:
            print(f"❌ Error: {system_info['error']}")
        else:
            print(f"💾 Disk Usage: {system_info.get('disk_usage', 'Unknown')}")
            print(
                f"🔄 Process Running: {'Yes' if system_info.get('process_running') else 'No'}")
            if system_info.get('process_ids'):
                print(
                    f"🆔 Process IDs: {', '.join(system_info['process_ids'])}")

        print()

        # Content Statistics
        print("📄 CONTENT STATISTICS")
        print("-" * 20)
        content_stats = self.get_generated_content_stats()

        if "error" in content_stats:
            print(f"❌ Error: {content_stats['error']}")
        else:
            print(
                f"📑 Total JSON Files: {content_stats.get('total_json_files', 0)}")
            print(
                f"📝 Total Markdown Files: {content_stats.get('total_md_files', 0)}")

            recent_files = content_stats.get('recent_files', [])
            if recent_files:
                print(f"\n📅 Recent Files (Last 7 days):")
                for file_info in recent_files:
                    print(
                        f"   • {file_info['filename']} ({file_info['size_kb']} KB) - {file_info['created']}")
            else:
                print("   No recent files found")

        print()

        # Recent Logs
        print("📋 RECENT LOGS (Last 10 lines)")
        print("-" * 30)
        logs = self.get_recent_logs(10)
        for log_line in logs:
            if log_line.strip():
                print(f"   {log_line}")

        print("\n" + "=" * 60)

    def watch_mode(self, interval: int = 30):
        """Run in watch mode, refreshing the dashboard every interval seconds"""
        try:
            while True:
                # Clear screen
                os.system('clear' if os.name == 'posix' else 'cls')

                self.display_dashboard()
                print(
                    f"\n🔄 Refreshing in {interval} seconds... (Press Ctrl+C to exit)")

                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n👋 Exiting monitor...")

    def start_agent(self):
        """Start the background agent"""
        try:
            print("🚀 Starting background agent...")
            process = subprocess.Popen(['python3', 'background_agent.py'])
            print(f"✅ Agent started with PID: {process.pid}")
        except Exception as e:
            print(f"❌ Error starting agent: {e}")

    def stop_agent(self):
        """Stop the background agent"""
        try:
            print("🛑 Stopping background agent...")
            result = subprocess.run(
                ['pkill', '-f', 'background_agent.py'], capture_output=True)
            if result.returncode == 0:
                print("✅ Agent stopped successfully")
            else:
                print("⚠️  No running agent process found")
        except Exception as e:
            print(f"❌ Error stopping agent: {e}")

    def run_once(self):
        """Run the agent once for testing"""
        try:
            print("🔄 Running agent once...")
            result = subprocess.run(
                ['python3', 'background_agent.py', '--run-once'])
            if result.returncode == 0:
                print("✅ Single run completed successfully")
            else:
                print("❌ Single run failed")
        except Exception as e:
            print(f"❌ Error running agent: {e}")


def main():
    parser = argparse.ArgumentParser(description='SEO Agent Monitor Dashboard')
    parser.add_argument('--config', default='agent_config.yaml',
                        help='Configuration file path')
    parser.add_argument('--watch', action='store_true',
                        help='Run in watch mode')
    parser.add_argument('--interval', type=int, default=30,
                        help='Refresh interval for watch mode (seconds)')
    parser.add_argument('--start', action='store_true',
                        help='Start the background agent')
    parser.add_argument('--stop', action='store_true',
                        help='Stop the background agent')
    parser.add_argument('--run-once', action='store_true',
                        help='Run the agent once for testing')
    parser.add_argument('--logs', type=int, default=20,
                        help='Number of log lines to show')

    args = parser.parse_args()

    monitor = AgentMonitor(args.config)

    if args.start:
        monitor.start_agent()
    elif args.stop:
        monitor.stop_agent()
    elif args.run_once:
        monitor.run_once()
    elif args.watch:
        monitor.watch_mode(args.interval)
    else:
        monitor.display_dashboard()


if __name__ == "__main__":
    main()
