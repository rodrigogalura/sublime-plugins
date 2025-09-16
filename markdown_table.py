import sublime
import sublime_plugin
import csv
import io

class GenerateMarkdownTableCommand(sublime_plugin.TextCommand):
    """
    Parses selected CSV-like text (auto-detects delimiter) or uses a default table,
    asks alignment per column, then delegates insertion to InsertMarkdownTableCommand.
    """
    def run(self, edit):
        region = self.view.sel()[0]
        selected_text = self.view.substr(region).strip()

        if selected_text:
            # Use a small sample for sniffing
            lines = selected_text.splitlines()
            sample = "\n".join(lines[:3]) if len(lines) > 0 else selected_text

            # Try sniffing delimiter
            delimiter = None
            try:
                sniffer = csv.Sniffer()
                dialect = sniffer.sniff(sample)
                delimiter = dialect.delimiter
            except Exception:
                # fallback: check header line for common delimiters
                header_line = lines[0] if lines else selected_text
                for d in [",", "\t", ";", "|"]:
                    if d in header_line:
                        delimiter = d
                        break
                if not delimiter:
                    delimiter = ","

            reader = csv.reader(io.StringIO(selected_text), delimiter=delimiter)
            data = list(reader)
            if not data:
                # nothing to do
                return

            self.headers = data[0]
            self.rows = data[1:]
        else:
            # default example table when nothing is selected
            self.headers = ["Name", "Age", "Country"]
            self.rows = [
                ["Alice", "25", "USA"],
                ["Bob", "30", "UK"],
                ["Charlie", "35", "Canada"]
            ]

        # normalize rows to have same number of columns as headers
        col_count = len(self.headers)
        normalized_rows = []
        for r in self.rows:
            row_copy = list(r)
            while len(row_copy) < col_count:
                row_copy.append("")
            if len(row_copy) > col_count:
                row_copy = row_copy[:col_count]
            normalized_rows.append(row_copy)
        self.rows = normalized_rows

        # prepare aligns (default left)
        self.aligns = ["left"] * len(self.headers)

        # store region positions (integers) for later insertion
        self.region_begin = region.begin()
        self.region_end = region.end()

        # start asking for alignment choices
        self.ask_alignment(0)

    def ask_alignment(self, index):
        if index >= len(self.headers):
            # finished — call insert command with collected data
            args = {
                "headers": self.headers,
                "rows": self.rows,
                "aligns": self.aligns,
                "region_begin": self.region_begin,
                "region_end": self.region_end
            }
            # view.run_command will call InsertMarkdownTableCommand.run with a fresh edit
            self.view.run_command("insert_markdown_table", args)
            return

        header = self.headers[index]
        options = [
            header + ": Left",
            header + ": Center",
            header + ": Right"
        ]

        def on_done(choice):
            if choice == -1:
                return  # cancelled by user
            if choice == 0:
                self.aligns[index] = "left"
            elif choice == 1:
                self.aligns[index] = "center"
            else:
                self.aligns[index] = "right"
            # ask next column
            self.ask_alignment(index + 1)

        # show quick panel for this column
        self.view.window().show_quick_panel(options, on_done)


class InsertMarkdownTableCommand(sublime_plugin.TextCommand):
    """
    Inserts or replaces the region with the generated markdown table.
    This command actually receives an `edit` object and performs the mutation.
    """
    def run(self, edit, headers, rows, aligns, region_begin, region_end):
        table = self.generate_markdown_table(headers, rows, aligns)
        region = sublime.Region(region_begin, region_end)
        if region.empty():
            self.view.insert(edit, region_begin, table)
        else:
            self.view.replace(edit, region, table)

    def generate_markdown_table(self, headers, rows, aligns):
        # Ensure all cells are strings
        headers = ["" if h is None else str(h) for h in headers]
        rows = [[("" if c is None else str(c)) for c in r] for r in rows]

        # Compute max width for each column
        col_count = len(headers)
        col_widths = [len(headers[i]) for i in range(col_count)]
        for r in rows:
            for i in range(col_count):
                cell = r[i] if i < len(r) else ""
                if len(cell) > col_widths[i]:
                    col_widths[i] = len(cell)

        # Helper to create the formatted row depending on alignment
        def format_row(row):
            parts = []
            for i in range(col_count):
                cell = row[i] if i < len(row) else ""
                align = aligns[i] if i < len(aligns) else "left"
                w = col_widths[i]
                if align == "right":
                    parts.append(cell.rjust(w))
                elif align == "center":
                    # str.center works in Python 3.3
                    parts.append(cell.center(w))
                else:
                    parts.append(cell.ljust(w))
            return "| " + " | ".join(parts) + " |"

        # Helper to create the alignment row
        def align_pattern(align, w):
            if w < 1:
                w = 1
            if align == "right":
                if w == 1:
                    return "-:"
                return "-" * (w - 1) + ":"
            elif align == "center":
                if w <= 2:
                    return ":-:"
                return ":" + "-" * (w - 2) + ":"
            else:  # left
                if w == 1:
                    return ":"
                return ":" + "-" * (w - 1)

        # Build table
        table_lines = []
        table_lines.append(format_row(headers))
        align_row_cells = [align_pattern(aligns[i] if i < len(aligns) else "left", col_widths[i]) for i in range(col_count)]
        table_lines.append("| " + " | ".join(align_row_cells) + " |")
        for r in rows:
            table_lines.append(format_row(r))

        return "\n".join(table_lines) + "\n"


class QuickGenerateTableCommand(sublime_plugin.TextCommand):
    """
    Quick command that inserts a small left-aligned example table at the cursor(s)
    or replaces the selection(s).
    """
    def run(self, edit):
        headers = ["Column 1", "Column 2", "Column 3"]
        rows = [
            ["Value 1", "Value 2", "Value 3"],
        ]
        aligns = ["left"] * len(headers)
        # Use the same generator for consistency
        inserter = InsertMarkdownTableCommand(self.view)
        table = inserter.generate_markdown_table(headers, rows, aligns)

        for region in self.view.sel():
            if region.empty():
                self.view.insert(edit, region.begin(), table)
            else:
                self.view.replace(edit, region, table)
