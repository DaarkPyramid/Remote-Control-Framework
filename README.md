# Remote Control Framework

A fully featured Python-based Remote Controller designed for automation, remote command 
execution, file management, and cross-platform interaction.  
This framework provides a stable and extensible communication channel between a server 
and multiple remote clients using a custom JSON-based protocol.

---

## 🚀 Features

### 🔗 **Custom Communication Protocol**
- Structured JSON messaging
- Delimiter-based parsing for stable transmission
- Handles partial/fragmented data without breaking the session
- Unique message IDs for tracking responses

### 🔄 **Smart Reconnection Logic**
- Automatic retry mechanism
- Configurable retry windows and intervals
- Graceful handling of timeouts and disconnections
- Keeps the client running 24/7 without crashes

### 🖥️ **Cross-Platform Command Execution**
- Supports Windows & Linux
- Automatic command mapping  
  (`ls → dir`, `clear → cls`, `cat → type`, etc.)
- Built-in working directory (CWD) management
- Output normalization for consistent formatting

### 📁 **Advanced File Transfer System**
- Streaming-based upload/download
- Uses Base64 chunking for reliability
- Supports large files without memory issues
- Verifies file boundaries using:
  - `file_start`
  - `file_chunk`
  - `file_end`

### 🔁 **Heartbeat Mechanism**
- Dedicated thread for sending periodic status signals
- Allows the server to monitor active clients
- Prevents idle timeouts and stale connections

### 🧩 **Clean & Modular Architecture**
- Message parser
- Connection layer
- File transfer module
- Command executor
- Windows installer/persistence engine
- Heartbeat service

Each component is isolated and easy to extend.

### 🪟 **Optional Windows Startup Persistence**
The client can optionally install itself into the user's:


Using:
- A copied version of the script  
- Auto-generated launcher `.bat` file  
- Safe file operations with full permissions

This enables automatic execution on system boot.

### 🧱 **Robust Error Handling**
- Handles connection drops
- Protects file writes
- Gracefully shuts down sessions
- Validates all JSON packets
- Ignores corrupted data without stopping execution

---

## 📚 Project Structure


Once connected, you can:
- Execute shell commands
- Upload or download files
- Navigate directories
- Receive structured responses
- Monitor client heartbeat

---

## ⚙️ Requirements

- Python 3.8+
- Works on:
  - Windows 7/10/11
  - Linux (any modern distro)
- No external dependencies

---

## 🔒 Legal & Ethical Notice

⚠️ **This project is intended for educational use, automation, lab environments, and**  
⚠️ **authorized penetration testing ONLY.**

You must **never** deploy this client/server framework on any device, system, or network  
without **explicit written permission** from the asset owner.

The author is **not responsible** for any misuse of this code.

---

## ⭐ Contributing

Pull requests are welcome.  
Feel free to open issues for improvements or suggestions.

---

## 📝 License

MIT License




