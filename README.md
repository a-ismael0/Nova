# Nova Clip - AI-Powered Content Generation Platform

Nova Clip is a Flask-based web application that automates the process of generating video content by scraping trending topics, creating AI-powered scripts, and collecting relevant images. The platform features a beautiful glassmorphism UI design and real-time processing updates.

## ✨ Features

- **Modern Web Interface**: Beautiful glassmorphism design with responsive mobile-friendly layout
- **Real-time Processing**: Live updates and progress tracking via WebSocket
- **AI-Powered Content Generation**: Uses OpenAI GPT-4 for intelligent script creation
- **Cross-Platform Support**: Runs on both Mac and Windows systems
- **Three-Stage Pipeline**:
  1. **Scraping**: Extract trending names from Google Trends TV with AI verification
  2. **Script Generation**: Create engaging YouTube video scripts with AI
  3. **Image Collection**: Gather high-quality relevant images using Google Custom Search

## 🚀 Quick Start

### Prerequisites

- Python 3.8+ (tested on Python 3.11)
- Chrome browser (for web scraping)
- API Keys:
  - OpenAI API Key (for GPT-4 script generation)
  - Google API Key (for Custom Search)
  - Google Custom Search Engine ID

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd nova-clip-flask
   ```

2. **Create virtual environment**:
   ```bash
   # On Mac/Linux
   python3 -m venv venv
   source venv/bin/activate
   
   # On Windows
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables** (optional):
   Create a `.env` file with your API keys:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   GOOGLE_API_KEY=your_google_api_key_here
   GOOGLE_CSE_ID=your_custom_search_engine_id_here
   SECRET_KEY=your_secret_key_here
   ```

5. **Configure API keys**:
   - Update `config.py` with your actual API keys
   - Update `modules/stage1_scraper.py` with your OpenAI API key
   - Update `modules/stage2_script_generator.py` with your OpenAI API key
   - Update `modules/stage3_image_generator.py` with your Google API keys

## 🎯 Usage

1. **Start the application**:
   ```bash
   python app.py
   ```

2. **Access the web interface**:
   - Open your browser and go to `http://localhost:5001`
   - Login with demo credentials: `user` / `user123`

3. **Run the processing pipeline**:
   - Select your target region/country
   - Click "Start Processing" to begin the three-stage pipeline
   - Monitor progress in real-time through the dashboard
   - Use "Stop Process" to halt processing at any time

4. **View results**:
   - Navigate to the Results page to see generated files
   - Download trends data (Excel files)
   - Download generated scripts (text files)
   - Browse image collections organized by person/topic

## 📁 Project Structure

```
nova-clip-flask/
├── app.py                          # Main Flask application
├── extensions.py                   # SocketIO configuration
├── config.py                      # Configuration settings
├── requirements.txt               # Python dependencies
├── static/
│   ├── styles.css                # Main CSS styles
│   ├── style_login.css           # Login page glassmorphism styles
│   ├── progress-bar_style.css    # Progress bar animations
│   ├── logo.png                  # Application logo
│   └── NC_ico.ico                # Favicon
├── templates/
│   ├── login.html                # Login page with glassmorphism design
│   ├── dashboard.html            # Main dashboard with real-time updates
│   ├── results.html              # Results viewer and file browser
│   └── browse_images.html        # Image gallery viewer
├── modules/
│   ├── __init__.py               # Package initialization
│   ├── orchestrator.py           # Main workflow controller
│   ├── stage1_scraper.py         # Google Trends scraper with AI verification
│   ├── stage2_script_generator.py # AI script generator
│   └── stage3_image_generator.py  # Enhanced image collector
├── auth/
│   └── users.json                # User authentication data
├── outputs/                      # Generated content storage
│   ├── trends_data/              # Scraped trends Excel files
│   ├── scripts/                  # Generated video scripts
│   └── images/                   # Downloaded image collections
├── README.md                     # This file
└── MAINTENANCE.md               # Maintenance and troubleshooting guide
```

## 🔧 Configuration

### User Management
Edit `auth/users.json` to add/modify user accounts:
```json
{
  "users": [
    {
      "username": "admin",
      "password": "admin123",
      "role": "administrator"
    }
  ]
}
```

### API Configuration
Update `config.py` with your API credentials:
- `OPENAI_API_KEY`: Your OpenAI API key for GPT-4 access
- `GOOGLE_API_KEY`: Your Google Cloud API key
- `GOOGLE_CSE_ID`: Your Custom Search Engine ID

## 🎨 Features in Detail

### Stage 1: Intelligent Scraping
- Extracts trending names from Google Trends TV
- Enriches data with Google search results and Wikipedia information
- Uses OpenAI GPT-4 to verify if names are real persons
- Filters results based on search volume (1M-20M results)
- Saves comprehensive data to Excel files

### Stage 2: AI Script Generation
- Creates engaging YouTube video scripts using GPT-4
- Generates video descriptions with hooks and CTAs
- Extracts visual keywords for image search
- Saves scripts and metadata in organized format
- Supports multiple video formats and durations

### Stage 3: Enhanced Image Collection
- Searches for relevant high-quality images using Google Custom Search
- Implements intelligent quality filtering and aspect ratio checking
- Downloads images with proper resolution requirements
- Maintains detailed image credits and source information
- Organizes images by person/topic in dedicated folders

### Real-time Dashboard
- Live progress tracking with animated progress bars
- Real-time log streaming via WebSocket
- Stage-by-stage status updates
- Connection status monitoring
- AI news feed integration
- Mobile-responsive glassmorphism design

## 🔒 Security Notes

- Change default login credentials in production
- Store API keys securely using environment variables
- Consider implementing proper user authentication with password hashing
- Review and update security settings before deployment
- Use HTTPS in production environments

## 🌐 Deployment

### Local Development
The application runs on `http://localhost:5001` by default.

### Production Deployment
For production deployment, consider:
- Using a production WSGI server (Gunicorn, uWSGI)
- Setting up reverse proxy (Nginx)
- Configuring SSL/TLS certificates
- Using environment variables for sensitive configuration
- Setting up proper logging and monitoring

### Recommended Hosting Platforms
- **Render**: Easy deployment with GitHub integration
- **PythonAnywhere**: Python-focused hosting
- **Heroku**: Popular platform-as-a-service
- **DigitalOcean App Platform**: Scalable cloud hosting
- **AWS/GCP/Azure**: Enterprise cloud solutions

## 🛠️ Troubleshooting

### Common Issues

1. **ChromeDriver Issues**: Ensure Chrome browser is installed and update ChromeDriver
2. **API Rate Limiting**: Check API quotas and implement proper delays
3. **Memory Issues**: Monitor memory usage during large processing runs
4. **File Permissions**: Ensure write permissions for output directories

### Debug Mode
Run with debug logging:
```bash
export FLASK_DEBUG=1
python app.py
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Check the [MAINTENANCE.md](MAINTENANCE.md) file for troubleshooting
- Open an issue in the repository
- Contact the development team

## 🙏 Acknowledgments

- OpenAI for GPT-4 API
- Google for Custom Search API
- Flask and SocketIO communities
- Bootstrap and modern CSS frameworks
- All contributors and testers

---

**Made with ♥ by Nova Clip Team**
