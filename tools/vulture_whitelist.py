"""Names vulture cannot see being used: framework hooks called by Textual, `http.server` and sqlite3."""

from typing import IO  # used in a string annotation

from asf_adapters.event_source import Hook
from asf_console.app import ConsoleApp
from asf_console.receiver import Server, make_handler
from asf_console.store import Store

IO
Hook.do_POST
Hook.log_message
ConsoleApp.TITLE
ConsoleApp.CSS
ConsoleApp.BINDINGS
ConsoleApp.on_mount
ConsoleApp.on_data_table_row_selected
ConsoleApp.on_tree_node_highlighted
ConsoleApp.action_clear_selection
Server.daemon_threads
Store.row_factory
handler = make_handler({})
handler.log_message
handler.do_GET
handler.do_POST
format
active = None  # TabbedContent.active
active
border_title = None  # RichLog.border_title
border_title
Violation = None  # factory.graph.Violation, used in a cast
Violation
