# ReMeDi Nova Spirometer Calibration App

A Python-based Streamlit application for calibrating ReMeDi Nova Spirometer devices via Bluetooth Low Energy (BLE) communication. This application performs spirometry data collection, mathematical calibration analysis, and coefficient optimization.

## Features

- 🔗 **Bluetooth Auto-Discovery**: Automatically scans and connects to SMSensor devices
- 📊 **Real-time Data Collection**: Records 6 sample types (pull/push fast/mid/slow)
- 🧮 **Mathematical Calibration**: Uses basis function models for pressure-to-flow conversion
- 🔄 **Auto-Recalibration**: Generates new coefficients if calibration fails
- 💾 **Database Persistence**: SQLite database for device and calibration history
- 📄 **PDF Reports**: Generate calibration reports for devices
- 🔌 **Auto-Reconnection**: Handles device power cycles gracefully

## Prerequisites

- Python 3.9 or higher
- Windows 10/11 (for Bluetooth support)
- SMSensor Bluetooth device

## Installation

### 1. Clone the Repository
```bash
git clone <repository-url>
cd Spirometry-Calibration-App
```

### 2. Create Virtual Environment
```bash
# Create virtual environment
python -m venv spirometry_env

# Activate virtual environment (Windows)
spirometry_env\Scripts\activate

# For Linux/Mac
# source spirometry_env/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Verify Installation
```bash
python -c "import streamlit, bleak, numpy; print('All dependencies installed successfully')"
```

## Usage

### Starting the Application

#### Method 1: Using main.py (Recommended)
```bash
python main.py
```

#### Method 2: Direct Streamlit
```bash
streamlit run ui_mod.py
```

### Application Workflow

1. **Device Connection**
   - App automatically scans for SMSensor devices on startup
   - Manual connection available via "Connect to Remedi Nova" button
   - Connection status displayed in real-time

2. **Device Registration**
   - Enter a unique Device ID when connecting for the first time
   - Device information stored in SQLite database

3. **Sample Recording**
   - Record 6 required samples: pull/push fast/mid/slow
   - Each sample records for 13 seconds
   - Data automatically saved to `Documents/Spirometer Calibration Logs/`

4. **Calibration Analysis**
   - Click "Run Calibration Check" after recording all 6 samples
   - Results show volume errors and pass/fail status (±3% tolerance)

5. **Auto-Recalibration** (if needed)
   - If calibration fails, use "Auto-Recalibrate" button
   - Generates new coefficients using mathematical optimization
   - Updates database with new coefficients

6. **Report Generation**
   - Download PDF reports for individual devices or all devices
   - Reports include calibration status, coefficients, and timestamps

## File Structure

```
Spirometry-Calibration-App/
├── main.py                 # Application entry point
├── ui_mod.py              # Main Streamlit UI application
├── calibration_check.py   # Calibration analysis engine
├── recalibration.py       # Coefficient generation
├── db.py                  # Database models and operations
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── CLAUDE.md             # Development documentation
├── .gitignore            # Git ignore rules
├── spirometry_env/       # Virtual environment (auto-created)
└── calibration.db        # SQLite database (auto-created)
```

## Configuration

### Bluetooth Settings
- Target device name: "SMSensor" or devices containing "SM"
- Characteristic UUID: `00003a05-0000-1000-8000-00805f9b34fb`
- Auto-reconnection enabled for power cycle handling

### Data Storage
- Log files: `%USERPROFILE%\Documents\Spirometer Calibration Logs\`
- Database: `calibration.db` (in app directory)
- Format: `{device_id}_{sample_type}_{timestamp}.log`

### Calibration Parameters
- Target volume: 3.0 Liters
- Sampling rate: 200 Hz (dt = 0.005)
- Error tolerance: ±3%
- 8-coefficient basis function model

## Troubleshooting

### Common Issues

1. **"Characteristic not found" error**
   - Ensure SMSensor device is powered on and in range
   - Try disconnecting and reconnecting the device
   - Check Windows Bluetooth settings

2. **Import errors**
   - Verify virtual environment is activated
   - Reinstall dependencies: `pip install -r requirements.txt`

3. **File saving issues**
   - Check folder permissions for Documents directory
   - Run "Test File Saving" button in the app

4. **Streamlit startup crash**
   - Ensure no other Streamlit instances are running
   - Check Python version compatibility (3.9+)

### Debug Mode
- Enable debug mode by running: `streamlit run ui_mod.py --logger.level debug`
- Check console output for detailed error messages
- Use "Show Debug Info" button in sidebar

## Development

### Architecture Overview
- **UI Layer**: Streamlit web interface (`ui_mod.py`)
- **Business Logic**: Calibration algorithms (`calibration_check.py`, `recalibration.py`)
- **Data Layer**: SQLite database operations (`db.py`)
- **Communication**: Bluetooth Low Energy via Bleak library

### Adding New Features
1. Review `CLAUDE.md` for development guidelines
2. Follow existing code patterns and conventions
3. Test with actual SMSensor devices
4. Update requirements.txt if adding new dependencies

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make changes following existing patterns
4. Test thoroughly with real devices
5. Submit a pull request

## License

[Add appropriate license information]

## Support

For technical support or questions:
- Check troubleshooting section above
- Review console output for error messages
- Ensure all prerequisites are met

## Version History

- **v1.0**: Initial release with basic calibration functionality
- **v1.1**: Added auto-reconnection and improved error handling
- **v1.2**: Enhanced UI and added PDF report generation