# Nova Clip - Maintenance Guide

This document provides comprehensive maintenance guidelines, troubleshooting information, and operational procedures for the Nova Clip application.

## 📋 Regular Maintenance Tasks

### Daily Tasks
- [ ] Monitor application logs for errors and warnings
- [ ] Check disk space in `outputs/` directories
- [ ] Verify API key quotas and usage limits
- [ ] Review real-time processing performance
- [ ] Check WebSocket connection stability

### Weekly Tasks
- [ ] Clean up old output files (older than 30 days)
- [ ] Review and rotate log files if needed
- [ ] Update dependencies if security patches are available
- [ ] Test all three processing stages
- [ ] Verify Chrome/ChromeDriver compatibility

### Monthly Tasks
- [ ] Review API usage and costs (OpenAI, Google)
- [ ] Update ChromeDriver if needed
- [ ] Backup important configuration files
- [ ] Review user access and permissions
- [ ] Performance optimization review

## 🔧 System Requirements

### Minimum Requirements
- **OS**: Windows 10+ or macOS 10.14+
- **Python**: 3.8+ (recommended: 3.11)
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 2GB free space for outputs
- **Browser**: Chrome/Chromium for web scraping

### Recommended Setup
- **OS**: Latest Windows 11 or macOS Monterey+
- **Python**: 3.11+
- **RAM**: 16GB for large processing runs
- **Storage**: 10GB+ for extensive image collections
- **Network**: Stable internet for API calls

## 🚨 Troubleshooting

### Common Issues

#### 1. SocketIO Connection Problems
**Symptoms**: Dashboard shows "Disconnected", real-time updates not working
**Solutions**:
```bash
# Check if port 5001 is available
netstat -an | grep 5001

# Restart the application
python app.py

# Check browser console for WebSocket errors
# Try different browser or clear cache
```

#### 2. ChromeDriver Issues
**Problem**: Selenium WebDriver fails to start
**Solutions**:
```bash
# Update ChromeDriver automatically
pip install --upgrade chromedriver-autoinstaller

# Check Chrome version compatibility
google-chrome --version  # Linux/Mac
# or check in Chrome: chrome://version/

# Manual ChromeDriver download if needed
# https://chromedriver.chromium.org/downloads
```

#### 3. API Rate Limiting
**Problem**: OpenAI or Google API requests failing
**Solutions**:
- Check API key quotas in respective dashboards
- Implement exponential backoff in requests
- Consider upgrading API plans if needed
- Monitor usage patterns and optimize calls

#### 4. Memory Issues
**Problem**: Application running out of memory during processing
**Solutions**:
```bash
# Monitor memory usage
top -p $(pgrep -f "python app.py")  # Linux/Mac
# or use Task Manager on Windows

# Reduce batch sizes in processing
# Implement garbage collection
# Consider processing in smaller chunks
```

#### 5. File Permission Errors
**Problem**: Cannot write to output directories
**Solutions**:
```bash
# Check directory permissions
ls -la outputs/

# Fix permissions (Mac/Linux)
chmod 755 outputs/
chmod 755 outputs/trends_data/
chmod 755 outputs/scripts/
chmod 755 outputs/images/

# Windows: Right-click folder → Properties → Security
```

#### 6. Image Download Failures
**Problem**: Stage 3 fails to download images
**Solutions**:
- Verify Google Custom Search API key and CSE ID
- Check API quotas and billing
- Test with smaller image counts
- Verify network connectivity
- Check image URL accessibility

### Error Codes Reference

#### Stage 1 Errors
- `SCRAPE_001`: No trending names found
  - Check Google Trends availability
  - Verify region parameter
  - Check network connectivity

- `SCRAPE_002`: WebDriver timeout
  - Increase timeout values
  - Check Chrome installation
  - Verify ChromeDriver compatibility

- `SCRAPE_003`: OpenAI verification failed
  - Check API key validity
  - Verify quota availability
  - Test with simpler requests

#### Stage 2 Errors
- `SCRIPT_001`: No valid persons found
  - Check filtering criteria in Stage 1
  - Verify search result thresholds
  - Review GPT verification logic

- `SCRIPT_002`: OpenAI script generation failed
  - Check API key and model availability
  - Verify prompt formatting
  - Test with shorter content

- `SCRIPT_003`: File save error
  - Check disk space availability
  - Verify write permissions
  - Check file path validity

#### Stage 3 Errors
- `IMAGE_001`: Google Custom Search failed
  - Verify API key and CSE ID
  - Check search quotas
  - Test API endpoints manually

- `IMAGE_002`: Image download failed
  - Check network connectivity
  - Verify image URL accessibility
  - Review download timeouts

- `IMAGE_003`: Storage error
  - Check disk space availability
  - Verify directory permissions
  - Review file naming conventions

## ⚡ Performance Optimization

### Database Optimization
```python
# Consider implementing SQLite for better data management
import sqlite3

# Create indexes for faster queries
# Implement connection pooling
# Regular cleanup of old records
```

### Caching Strategies
```python
# Implement Redis for session management
import redis

# Cache API responses where appropriate
# Use CDN for static assets in production
# Implement request deduplication
```

### Memory Management
```python
# Implement garbage collection
import gc

# Monitor memory usage
import psutil

# Use generators for large datasets
# Implement streaming for file processing
```

### API Optimization
```python
# Implement request batching
# Use async requests where possible
# Implement proper retry logic with exponential backoff
# Cache frequently used API responses
```

## 📊 Monitoring and Logging

### Application Monitoring
```python
# Set up health check endpoints
@app.route('/health')
def health_check():
    return {'status': 'healthy', 'timestamp': datetime.now().isoformat()}

# Monitor API usage and costs
# Track processing success rates
# Monitor WebSocket connection stability
```

### Log Management
```python
import logging
from logging.handlers import RotatingFileHandler

# Configure rotating log files
handler = RotatingFileHandler('logs/app.log', maxBytes=10000000, backupCount=5)
app.logger.addHandler(handler)
```

### Key Metrics to Monitor
- Processing success rates by stage
- API call frequency and costs
- Memory and CPU usage
- WebSocket connection stability
- File system usage
- User activity patterns

## 🔒 Security Maintenance

### Regular Security Tasks
- [ ] Update all dependencies monthly
- [ ] Review and rotate API keys quarterly
- [ ] Audit user access and permissions
- [ ] Monitor for suspicious activity
- [ ] Review error logs for security issues

### Security Checklist
- [ ] All API keys stored securely (environment variables)
- [ ] HTTPS enabled in production
- [ ] Input validation implemented
- [ ] Rate limiting configured
- [ ] Error messages don't expose sensitive info
- [ ] File upload restrictions in place
- [ ] User authentication properly implemented
- [ ] Session management secure

### API Key Security
```bash
# Rotate API keys regularly
# Use environment variables
export OPENAI_API_KEY="your-new-key"
export GOOGLE_API_KEY="your-new-key"

# Monitor API usage for anomalies
# Set up billing alerts
# Implement key rotation procedures
```

## 💾 Backup and Recovery

### Backup Strategy
```bash
# Configuration Files (Daily)
tar -czf backups/config-$(date +%Y%m%d).tar.gz config.py auth/ templates/

# Output Files (Weekly)
tar -czf backups/outputs-$(date +%Y%m%d).tar.gz outputs/

# Database (if implemented)
sqlite3 database.db ".backup backups/db-$(date +%Y%m%d).db"
```

### Recovery Procedures
1. **Application Failure**: 
   - Restart service
   - Check logs for errors
   - Verify dependencies

2. **Data Loss**: 
   - Restore from latest backup
   - Verify data integrity
   - Resume processing if needed

3. **API Key Compromise**: 
   - Immediately rotate keys
   - Review usage logs
   - Update configuration

4. **Server Failure**: 
   - Deploy to backup server
   - Restore from backups
   - Update DNS if needed

## 🚀 Deployment Maintenance

### Production Deployment Checklist
- [ ] Environment variables configured
- [ ] SSL certificates installed
- [ ] Reverse proxy configured (Nginx)
- [ ] Process manager setup (systemd, supervisor)
- [ ] Log rotation configured
- [ ] Monitoring tools installed
- [ ] Backup procedures tested
- [ ] Security hardening applied

### Staging Environment
- [ ] Mirror production configuration
- [ ] Separate API keys for testing
- [ ] Test all updates before production
- [ ] Automated testing pipeline
- [ ] Performance testing

### Update Procedures
```bash
# 1. Backup current version
cp -r nova-clip-flask nova-clip-flask-backup

# 2. Pull latest changes
git pull origin main

# 3. Update dependencies
pip install -r requirements.txt

# 4. Test in staging
python app.py

# 5. Deploy to production
# (Use your deployment method)

# 6. Verify deployment
curl http://localhost:5001/health
```

## 📞 Emergency Contacts

### Development Team
- **Lead Developer**: [Contact Info]
- **DevOps Engineer**: [Contact Info]
- **System Administrator**: [Contact Info]

### Emergency Procedures
- **Critical Bug**: Contact lead developer immediately
- **Security Incident**: Follow security incident response plan
- **Service Outage**: Check monitoring dashboard, contact on-call engineer

### Escalation Matrix
1. **Level 1**: Application errors, minor issues
2. **Level 2**: Service degradation, API failures
3. **Level 3**: Complete service outage, security incidents

## 📈 Version History

| Version | Date | Changes | Maintainer |
|---------|------|---------|------------|
| 2.0.0 | 2025-01-XX | Glassmorphism UI, Enhanced SocketIO | Development Team |
| 1.5.0 | 2025-01-XX | Image quality improvements | Development Team |
| 1.0.0 | 2025-01-XX | Initial release | Development Team |

## 📚 Additional Resources

### Documentation Links
- [Flask Documentation](https://flask.palletsprojects.com/)
- [SocketIO Documentation](https://python-socketio.readthedocs.io/)
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [Google Custom Search API](https://developers.google.com/custom-search)

### Useful Commands
```bash
# Check Python version
python --version

# List installed packages
pip list

# Check disk usage
df -h

# Monitor processes
ps aux | grep python

# Check network connections
netstat -tulpn | grep :5001

# View recent logs
tail -f logs/app.log
```

---

**Last Updated**: January 2025  
**Next Review**: February 2025  
**Maintained by**: Nova Clip Development Team