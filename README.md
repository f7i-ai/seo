# SEO Content Generator Background Agent

A robust background service for automatically generating SEO-optimized content using AI. This system processes keywords from Ahrefs CSV exports, researches them using Google Gemini 2.5 Pro, generates high-quality content, and saves it in multiple formats.

## 🚀 Features

- **Automated Processing**: Runs on schedule (default: daily at 2 AM)
- **Intelligent Filtering**: Avoids duplicates and content overlap
- **Comprehensive Research**: Uses Google Gemini 2.5 Pro for deep keyword research with SERP analysis
- **Multi-format Output**: Saves content as JSON (for Prismic CMS) and Markdown
- **Image Generation**: Creates hero images using OpenAI DALL-E
- **Robust Error Handling**: Retry logic and comprehensive logging
- **Monitoring Dashboard**: Real-time status monitoring
- **Email Notifications**: Optional email alerts for success/failure
- **Rate Limiting**: Respects API limits with configurable delays
- **Queue Management**: Processes multiple keywords concurrently

## 📋 Prerequisites

- Python 3.8+
- Google Gemini 2.5 Pro API key (for content generation and research)
- OpenAI API key (for DALL-E image generation)
- Ahrefs CSV export with keyword data

## 🛠️ Installation

1. **Clone or download the project files**

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:
   Create a `.env` file in the project root:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   OPENAI_API_KEY=your_openai_api_key_here
   ```

4. **Configure the agent**:
   Edit `agent_config.yaml` to customize settings (see Configuration section)

## ⚙️ Configuration

The agent is configured via `agent_config.yaml`. Key settings include:

### Processing Settings
```yaml
max_keywords_per_run: 5          # Keywords to process per cycle
concurrent_workers: 2            # Parallel processing threads
retry_attempts: 3                # Retries for failed keywords
rate_limit_delay: 5              # Seconds between API calls
```

### Scheduling
```yaml
run_interval_hours: 24           # How often to run (hours)
run_at_hour: 2                   # What hour to run (24h format)
```

### Email Notifications (Optional)
```yaml
email_notifications: true
smtp_server: "smtp.gmail.com"
smtp_port: 587
email_user: "your-email@gmail.com"
email_password: "your-app-password"
notification_recipients:
  - "admin@yourdomain.com"
```

## 🏃‍♂️ Usage

### Running the Background Agent

1. **Start the agent**:
   ```bash
   python3 background_agent.py
   ```

2. **Run once for testing**:
   ```bash
   python3 background_agent.py --run-once
   ```

3. **Check status**:
   ```bash
   python3 background_agent.py --status
   ```

### Using the Monitor Dashboard

The monitoring dashboard provides real-time insights:

1. **View current status**:
   ```bash
   python3 monitor_dashboard.py
   ```

2. **Live monitoring (updates every 30 seconds)**:
   ```bash
   python3 monitor_dashboard.py --watch
   ```

3. **Control the agent**:
   ```bash
   # Start agent
   python3 monitor_dashboard.py --start
   
   # Stop agent
   python3 monitor_dashboard.py --stop
   
   # Run once
   python3 monitor_dashboard.py --run-once
   ```

### Running as a System Service (Linux)

1. **Edit the service file**:
   Update paths in `seo-agent.service`:
   ```bash
   sudo nano seo-agent.service
   ```

2. **Install the service**:
   ```bash
   sudo cp seo-agent.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable seo-agent
   ```

3. **Start the service**:
   ```bash
   sudo systemctl start seo-agent
   ```

4. **Check service status**:
   ```bash
   sudo systemctl status seo-agent
   sudo journalctl -u seo-agent -f
   ```

## 📁 File Structure

```
seo/
├── background_agent.py          # Main background agent
├── monitor_dashboard.py         # Monitoring dashboard
├── seo_content_generator.py     # Core content generation logic
├── agent_config.yaml           # Configuration file
├── seo-agent.service           # Systemd service file
├── kw.csv                      # Keywords CSV (Ahrefs export)
├── requirements.txt            # Python dependencies
├── .env                        # Environment variables
├── generated_content/          # Output directory
│   ├── *.json                 # Prismic-formatted content
│   └── *.md                   # Markdown content
└── logs/                       # Log files
    └── agent_YYYYMMDD.log     # Daily log files
```

## 📊 Output Formats

### JSON Output (Prismic CMS)
```json
{
  "meta_title": "Understanding CMMS: Complete Guide...",
  "meta_description": "Learn everything about...",
  "title": "What is CMMS? Complete Guide to...",
  "keyword": "cmms meaning",
  "hero_image": {
    "url": "https://...",
    "alt": "Hero image for..."
  },
  "body": [...],
  "internal_references": [...],
  "external_references": [...]
}
```

### Markdown Output
```markdown
# What is CMMS? Complete Guide to Computerized Maintenance Management Systems

**Keyword:** cmms meaning
**Meta Title:** Understanding CMMS: Complete Guide...
**Meta Description:** Learn everything about...

---

[Article content in markdown format]

## Internal Link Suggestions
1. **Preventive Maintenance** → `/blog/preventive-maintenance-guide`

## External Reference Links
1. **ISO 55000 Standard** → [https://www.iso.org/iso-55001-asset-management.html](...)
```

## 📈 Monitoring & Logging

### Dashboard Features
- **Agent Status**: Running state, next scheduled run, processing statistics
- **System Info**: Disk usage, process status
- **Content Stats**: Total files generated, recent activity
- **Recent Logs**: Last 10 log entries

### Log Files
- Located in `logs/` directory
- Daily rotation: `agent_YYYYMMDD.log`
- Comprehensive logging of all operations
- Error tracking and performance metrics

## 🔧 Troubleshooting

### Common Issues

1. **"No keywords found in CSV"**
   - Check CSV format and encoding
   - Ensure CSV has proper column headers
   - Try different delimiters (comma vs tab)

2. **API rate limits**
   - Increase `rate_limit_delay` in config
   - Reduce `concurrent_workers`

3. **Memory issues**
   - Reduce `max_keywords_per_run`
   - Lower `concurrent_workers`

4. **Permission errors**
   - Check file permissions on output directories
   - Ensure proper user permissions for systemd service

### Debug Mode
Enable debug logging by modifying the logging level in `background_agent.py`:
```python
self.logger.setLevel(logging.DEBUG)
```

## 🔐 Security Considerations

- Store API keys in environment variables, not in code
- Use app passwords for email notifications
- Set appropriate file permissions (600) for `.env`
- Run service with minimal required privileges
- Regularly rotate API keys

## 📞 Support

For issues or questions:
1. Check the logs in `logs/` directory
2. Use the monitor dashboard for real-time status
3. Review configuration settings
4. Check API key validity and quotas

## 🔄 Updates

To update the system:
1. Stop the agent: `sudo systemctl stop seo-agent`
2. Update code files
3. Install new dependencies: `pip install -r requirements.txt`
4. Start the agent: `sudo systemctl start seo-agent`

## 📝 License

This project is proprietary software for f7i.ai content generation. 