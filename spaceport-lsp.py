import json
import threading
import sublime
import sublime_plugin
import websocket
import urllib.parse
import time
import ssl

# WebSocket LSP for use with Spaceport and Sublime Text.

class WebSocketLspClient:
    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.ws = None
        self.request_id = 0
        self.pending_requests = {}
        self.running = False
        self.connected = False
        self.sslopt = {"cert_reqs": ssl.CERT_NONE, "check_hostname": False}

    def connect(self):
        try:
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
                on_open=self.on_open
            )
            self.running = True
            threading.Thread(target=self.ws.run_forever, daemon=True, kwargs={'sslopt': self.sslopt}).start()
            return True  # Return True on successful connection thread start
        except Exception as e:
            print("Failed to connect to Spaceport LSP server: {}".format(e))
            sublime.error_message("Failed to connect to Spaceport LSP server: {}".format(e))
            self.disconnect() # disconnect if connect fails
            return False

    def disconnect(self):
        self.running = False
        self.connected = False
        if self.ws:
            self.ws.close()
            self.ws = None
        global lsp_client  # Correctly reference the global client
        print("Disconnected from Spaceport LSP server.")
        lsp_client = None

    def send_request(self, method, params, callback=None):
        if not self.connected:
           print("Not connected to the server")
           return
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params,
            "handler-id": "SpaceportLSP"
        }
        if callback:
            self.pending_requests[self.request_id] = callback
        self.send_message(request)

    def send_notification(self, method, params):
        if not self.connected:
            print("Not connected to the server")
            return
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "handler-id": "SpaceportLSP"
        }
        self.send_message(notification)

    def send_message(self, message):
        if not self.connected:
            print("Not connected to the Spaceport LSP server")
            return
        try:
            self.ws.send(json.dumps(message))
        except Exception as e:
            print("Error sending message: {}".format(e))
            self.disconnect()

    def on_message(self, ws, message_str):
        print("Received message: {}".format(message_str))
        try:
            message = json.loads(message_str)
            self.handle_message(message)
        except (ValueError, AttributeError) as e:
            print("Error decoding message: {}, message: {}".format(e, message_str))

    def on_error(self, ws, error):
        print("WebSocket error: {}".format(error))


    def on_close(self, ws, close_status_code=None, close_msg=None):
        print("WebSocket connection closed.")
        self.disconnect()
        if self.running:
            sublime.error_message(
                "Websocket connection to Spaceport LSP server closed unexpectedly: {}".format(
                    close_msg
                )
            )

    def on_open(self, ws):
        print("Connected to LSP server at {}".format(self.ws_url))
        self.connected = True
        self.initialize()

    def handle_message(self, message):
        if "id" in message:
            request_id = message["id"]
            if request_id in self.pending_requests:
                callback = self.pending_requests.pop(request_id)
                if "result" in message:
                    callback(message["result"])
                elif "error" in message:
                    callback(message["error"])
        elif "method" in message:
            self.handle_notification(message)

    def handle_notification(self, notification):
        method = notification["method"]
        params = notification.get("params", {})
        if method == "textDocument/publishDiagnostics":
            self.handle_diagnostics(params)
        elif method == "window/logMessage":
            print("LSP Server Log: {}".format(params.get("message")))
        else:
            print("Received notification: {} - {}".format(method, params))

    def handle_diagnostics(self, params):
        uri = params.get("uri")
        diagnostics = params.get("diagnostics", [])
        print("Diagnostics for {}: {}".format(uri, diagnostics))


    def initialize(self):
        params = {
            "processId": None,
            "clientInfo": {"name": "SublimeTextLSPClient"},
            "capabilities": {
                "textDocument": {
                    "completion": {
                        "completionItem": {
                            "snippetSupport": True
                        }
                    }
                }
            },
            "rootUri": None,  #  Could be set, but needs careful handling
            "workspaceFolders": None, # Could be set with sublime.active_window().folders()
        }
        self.send_request("initialize", params, self.handle_initialize_response)

    def handle_initialize_response(self, result):
        print("Initialized LSP Server")
        self.send_notification("initialized", {})
        self.send_open_documents()

    def send_open_documents(self):
        window = sublime.active_window()
        for view in window.views():
            if view.file_name():
                self.send_did_open(view)

    def send_did_open(self, view):
        params = {
            "textDocument": {
                "uri": self.get_file_uri(view),
                "languageId": view.settings().get("syntax").split('/')[-1].split('.')[0].lower(),
                "version": 1,  #  Version should be incremented on changes
                "text": view.substr(sublime.Region(0, view.size())),
            }
        }
        self.send_notification("textDocument/didOpen", params)

    def get_file_uri(self, view):
        file_path = view.file_name()
        if file_path:
            return "file://{}".format(urllib.parse.quote(file_path, safe="/:"))
        return ""



lsp_client = None  # Initialize lsp_client globally


def plugin_loaded():
    print("SpaceportLSP plugin loaded")
    global lsp_client
    settings = sublime.load_settings("Spaceport.sublime-settings")
    spaceport_address = settings.get("spaceport_address")
    if spaceport_address:  # Only connect if address is set
      lsp_client = WebSocketLspClient(spaceport_address)
      lsp_client.connect()
    else:
        print("Spaceport address not configured.")

def plugin_unloaded():
    global lsp_client
    if lsp_client:
        lsp_client.disconnect()
        lsp_client = None



class WebSocketLspConnectCommand(sublime_plugin.WindowCommand):
    def run(self):
        global lsp_client
        if lsp_client is None:
            settings = sublime.load_settings("Spaceport.sublime-settings")
            spaceport_address = settings.get("spaceport_address")
            if spaceport_address:
              lsp_client = WebSocketLspClient(spaceport_address)
              lsp_client.connect()
            else:
                sublime.error_message("Spaceport address not configured.")

    def is_enabled(self):
        global lsp_client
        return lsp_client is None

    def description(self):
        return "Connect to Spaceport LSP Server"

class WebSocketLspDisconnectCommand(sublime_plugin.WindowCommand):
    def run(self):
        global lsp_client
        if lsp_client:
            lsp_client.disconnect()
            lsp_client = None

    def is_enabled(self):
        global lsp_client
        return lsp_client is not None

    def description(self):
        return "Disconnect from Spaceport LSP Server"

class SpaceportSettingsListener(sublime_plugin.EventListener):
    def on_post_save(self, view):
        settings_file = "Spaceport.sublime-settings"
        if view.file_name() and view.file_name().endswith(settings_file):
            print("Spaceport settings saved, reloading LSP connection.")
            global lsp_client

            # Reload settings to get the updated values.
            settings = sublime.load_settings(settings_file)
            spaceport_address = settings.get("spaceport_address")

            if not spaceport_address:
                sublime.error_message("Spaceport address not configured!")
                return # Exit if no address

            if lsp_client:
                lsp_client.disconnect()

            try:
                lsp_client = WebSocketLspClient(spaceport_address)
                if not lsp_client.connect():  # Check the connection.
                    sublime.error_message("Failed to connect to Spaceport LSP server.")
                    lsp_client = None  # Set to None if connection fails

            except Exception as e:
                sublime.error_message("Error connecting to Spaceport: {}".format(e))
                lsp_client = None

class WebSocketLspEventListener(sublime_plugin.EventListener):
    def __init__(self):
        self.last_change_time = 0
        self.debounce_delay = 200  # Milliseconds
        self.completions = []
        self.completion_ready = False
        self.view = None
        self._next_completion_request_location = None

    def on_modified_async(self, view):
        self.handle_did_change(view)


    def handle_did_change(self, view):
        global lsp_client
        if not lsp_client or not view.file_name() or not lsp_client.connected:
            return

        current_time = int(time.time() * 1000)
        if current_time - self.last_change_time < self.debounce_delay:
            return

        self.last_change_time = current_time
        params = {
            "textDocument": {
                "uri": lsp_client.get_file_uri(view)
            },
            "contentChanges": [{
                "text": view.substr(sublime.Region(0, view.size()))
            }]
        }

        lsp_client.send_notification("textDocument/didChange", params)

    def on_query_completions(self, view, prefix, locations):
        print("on_query_completions triggered", prefix, locations)

        global lsp_client
        if not lsp_client or not view.file_name() or not lsp_client.connected:
            return []

        self.view = view
        self._next_completion_request_location = locations[0]

        if self.completion_ready and self.view == view:
            self.completion_ready = False
            print("Returning cached completions")
            return (self.completions, 0)  # Return cached completions

        # If no cached completions, request them.
        self.request_completions(view, locations)
        return ([], sublime.DYNAMIC_COMPLETIONS)

    def request_completions(self, view, locations):
        cursor_pos = locations[0]
        line, col = view.rowcol(cursor_pos)
        trigger_char = ""
        if col > 0:
          trigger_char = view.substr(sublime.Region(cursor_pos - 1, cursor_pos))
        print("trigger_char {}".format(trigger_char))

        params = {
            "textDocument": {"uri": lsp_client.get_file_uri(view)},
            "position": {"line": line, "character": col},
            "context": {
                "triggerKind": 2 if trigger_char else 1,
                "triggerCharacter": trigger_char
            },
        }
        lsp_client.send_request(
            "textDocument/completion", params, self.handle_completion_response
        )

    def handle_completion_response(self, result):
        if result is None:
            self.completions = []
            return

        completions = []

        if isinstance(result, dict) and "items" in result:
            items = result["items"]
            is_incomplete = result.get("isIncomplete", False)
        elif isinstance(result, list):
            items = result
            is_incomplete = False
        else:
            print("Unexpected completion result format: {}".format(result))
            self.completions = []
            return

        for item in items:
            label = item.get("label", "")
            detail = item.get("detail", "")
            insert_text = item.get("insertText", label)  # Fallback to label

            if "textEdit" in item:
                text_edit = item["textEdit"]
                if "range" in text_edit and "newText" in text_edit:
                    insert_text = text_edit["newText"]

            if item.get("insertTextFormat") == 2:  # Snippet
                insert_text = self.convert_lsp_snippet_to_sublime(insert_text)

            completions.append(("{}\t{}".format(label, detail), insert_text))

        if is_incomplete:
            print("Completions were incomplete")

        print("Completions: {}".format(completions))
        self.completions = completions
        self.completion_ready = True

        # Trigger auto_complete ONLY if the cursor is still at the location we requested
        if self.view and self._next_completion_request_location == self.view.sel()[0].begin():
           sublime.set_timeout(lambda: self.view.run_command('auto_complete'), 0)


    def convert_lsp_snippet_to_sublime(self, lsp_snippet):
        # Basic conversion:  Replace LSP placeholders with Sublime placeholders.
        sublime_snippet = lsp_snippet.replace("\\$", "$")  # Escape $
        sublime_snippet = sublime_snippet.replace("${", "$") # Replace start
        sublime_snippet = sublime_snippet.replace("}", "")   # Remove end curly
        return sublime_snippet
