import ttkbootstrap as tk
from ttkbootstrap import ttk
from tkinter import filedialog, messagebox, Menu
import re
import os
import configparser
import subprocess
import shutil

# --- Constants & Configuration ---
APP_TITLE = "Dohna Dohna Translation Helper v6.2 (Comma Fix)"
THEME_NAME = "flatly"
FONT_MAIN = ("Consolas", 10)
CONFIG_FILE = "dohnatool.ini"

# Regex patterns
REGEX_EVENT = re.compile(r'^; ＥＶ／(.*)$')

# FIX: Make the semicolon optional (^;?) so it detects IDs in saved files too
REGEX_ANCHOR = re.compile(r'^;?s\[\d+\]\s*=\s*"(\d+)"')
REGEX_MSG_COMMENTED = re.compile(r'^;\s*([sm]\[\d+\]\s*=.*)$')

# --- HONORIFICS CONFIGURATION ---
SUFFIX_HONORIFICS = [
    "さん", "ちゃん", "くん", "君", "様", "さま", "殿", "氏"
]

ROMAJI_HONORIFICS = [
    "san", "chan", "kun", "sama", "dono", "onii", "onee", "aniki", "aneki"
]

STANDALONE_HONORIFICS = [
    "先輩", "先生", "博士", "お兄", "お姉", "兄貴", "姉貴",
    "アニキ", "アネキ", "にぃ", "ねぇ", "ニィ", "ネェ",
    "父", "母", "おじ", "おば"
]

DEFAULT_HONORIFICS = SUFFIX_HONORIFICS + ROMAJI_HONORIFICS + STANDALONE_HONORIFICS

class SceneBlock:
    def __init__(self, raw_header):
        self.header = raw_header.strip()
        self.lines = []

    def add_line(self, line):
        self.lines.append(line)

    def get_content(self):
        return "".join(self.lines)

class DohnaTool(tk.Window):
    def __init__(self):
        super().__init__(themename=THEME_NAME)
        self.title(APP_TITLE)

        # State
        self.jp_scenes = {}
        self.en_scenes = {}
        self.scene_order = []
        self.current_scene_key = None
        self.unsaved_changes = False

        # Config Data
        self.scene_statuses = {}
        self.active_honorifics = DEFAULT_HONORIFICS.copy()
        self.exception_phrases = []

        # Patterns
        self.honorifics_pattern = None
        self.comma_honorifics_pattern = None # NEW: For "、さん" cases
        self.exceptions_pattern = None

        self.global_search_enabled = False

        # Paths
        self.last_jp_path = ""
        self.last_en_path = ""
        self.win_geometry = "1400x900"

        self.load_config()
        self.geometry(self.win_geometry)

        self.rebuild_regex()

        # Icons
        self.blue_dot_img = tk.PhotoImage(width=12, height=12)
        self.blue_dot_img.put("#2196F3", to=(3, 3, 9, 9))

        # NEW: Purple Dot Icon
        self.purple_dot_img = tk.PhotoImage(width=12, height=12)
        self.purple_dot_img.put("#9C27B0", to=(3, 3, 9, 9))

        self._init_gui()

        # Auto-load
        if self.last_jp_path and os.path.exists(self.last_jp_path):
            self.load_jp_file(self.last_jp_path)
        if self.last_en_path and os.path.exists(self.last_en_path):
            self.load_en_file(self.last_en_path)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _init_gui(self):
        # --- Top Toolbar ---
        toolbar = ttk.Frame(self, padding=5)
        toolbar.pack(fill=tk.X, side=tk.TOP)

        # Row 1
        row1 = ttk.Frame(toolbar)
        row1.pack(fill=tk.X, pady=2)

        ttk.Button(row1, text="Load JP", command=lambda: self.load_jp_file(), bootstyle="secondary").pack(side=tk.LEFT, padx=2)
        ttk.Button(row1, text="Load EN", command=lambda: self.load_en_file(), bootstyle="primary").pack(side=tk.LEFT, padx=2)
        ttk.Button(row1, text="Save EN", command=self.save_en_file, bootstyle="success").pack(side=tk.LEFT, padx=2)

        ttk.Separator(row1, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)

        ttk.Button(row1, text="Build .AIN", command=self.build_ain_file, bootstyle="danger").pack(side=tk.LEFT, padx=2)

        ttk.Separator(row1, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)

        ttk.Label(row1, text="Mark:").pack(side=tk.LEFT, padx=5)
        ttk.Button(row1, text="Finish (Green)", command=lambda: self.set_scene_status("green"), bootstyle="success-outline").pack(side=tk.LEFT, padx=2)
        ttk.Button(row1, text="Review (Orange)", command=lambda: self.set_scene_status("orange"), bootstyle="warning-outline").pack(side=tk.LEFT, padx=2)
        ttk.Button(row1, text="Clear", command=lambda: self.set_scene_status("none"), bootstyle="secondary-outline").pack(side=tk.LEFT, padx=2)

        ttk.Button(row1, text="Settings", command=self.open_settings, bootstyle="dark").pack(side=tk.RIGHT, padx=5)

        # Row 2
        row2 = ttk.Frame(toolbar)
        row2.pack(fill=tk.X, pady=2)

        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.filter_scene_list)
        ttk.Label(row2, text="Search:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(row2, textvariable=self.search_var, width=30).pack(side=tk.LEFT, padx=5)

        # Next Honorific
        ttk.Button(row2, text="Next Honorific ->", command=self.jump_next_honorific, bootstyle="info-outline").pack(side=tk.RIGHT, padx=2)
        self.btn_highlight = ttk.Button(row2, text="Highlight Honorifics", command=self.toggle_honorifics, bootstyle="info")
        self.btn_highlight.pack(side=tk.RIGHT, padx=5)

        # --- Main Layout ---
        self.paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 1. Sidebar
        sidebar_frame = ttk.Frame(self.paned)
        self.paned.add(sidebar_frame, weight=1)

        self.tree = ttk.Treeview(sidebar_frame, columns=("id"), show="tree", selectmode="browse")
        self.tree.column("#0", width=250)
        self.tree.heading("#0", text="Scenes")

        tree_scroll = ttk.Scrollbar(sidebar_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self.on_scene_select)

        self.tree.tag_configure('green', background='#d4edda')
        self.tree.tag_configure('orange', background='#fff3cd')

        # 2. Editor Area
        editor_frame = ttk.Frame(self.paned)
        self.paned.add(editor_frame, weight=4)

        self.scr_v = ttk.Scrollbar(editor_frame, orient=tk.VERTICAL, command=self.sync_scroll_y)
        self.scr_v.pack(side=tk.RIGHT, fill=tk.Y)

        editor_splitter = ttk.PanedWindow(editor_frame, orient=tk.HORIZONTAL)
        editor_splitter.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        jp_group = ttk.Labelframe(editor_splitter, text="Japanese (Reference)", padding=5)
        editor_splitter.add(jp_group, weight=1)
        self.txt_jp = tk.Text(jp_group, font=FONT_MAIN, wrap=tk.NONE, bg="#f4f4f4")

        en_group = ttk.Labelframe(editor_splitter, text="English (Editable)", padding=5)
        editor_splitter.add(en_group, weight=1)
        self.txt_en = tk.Text(en_group, font=FONT_MAIN, wrap=tk.NONE, undo=True)
        self.txt_en.bind("<<Modified>>", self.on_text_modified)

        self.txt_jp.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        self.txt_en.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        scr_jp_h = ttk.Scrollbar(jp_group, orient=tk.HORIZONTAL, command=self.txt_jp.xview)
        scr_jp_h.pack(side=tk.BOTTOM, fill=tk.X)
        self.txt_jp.config(xscrollcommand=scr_jp_h.set)

        scr_en_h = ttk.Scrollbar(en_group, orient=tk.HORIZONTAL, command=self.txt_en.xview)
        scr_en_h.pack(side=tk.BOTTOM, fill=tk.X)
        self.txt_en.config(xscrollcommand=scr_en_h.set)

        for widget in [self.txt_jp, self.txt_en]:
            widget.bind("<MouseWheel>", self.on_mousewheel)
            widget.bind("<Button-4>", self.on_mousewheel)
            widget.bind("<Button-5>", self.on_mousewheel)
            widget.config(yscrollcommand=self.sync_scroll_set)

        self.txt_jp.tag_configure("honorific", background="#aeeaff", foreground="black")
        self.txt_jp.tag_configure("honorific_comma", background="#E1BEE7", foreground="#4A148C") # Light Purple bg
        self.txt_jp.tag_configure("active_honorific", background="#4facfe", underline=True, foreground="black")

    # --- Scrolling ---
    def sync_scroll_y(self, *args):
        self.txt_jp.yview(*args)
        self.txt_en.yview(*args)

    def sync_scroll_set(self, *args):
        self.scr_v.set(*args)

    def on_mousewheel(self, event):
        if event.delta:
            move = int(-1*(event.delta/120))
        elif event.num == 4:
            move = -1
        elif event.num == 5:
            move = 1
        else:
            return
        self.txt_jp.yview_scroll(move, "units")
        self.txt_en.yview_scroll(move, "units")
        return "break"

    # --- Honorifics & Settings ---
    def rebuild_regex(self):
        # 1. Standard Honorifics Regex (Blue Dot)
        if not self.active_honorifics:
            self.honorifics_pattern = None
            self.comma_honorifics_pattern = None
        else:
            # --- Build Blue Dot Pattern (Normal) ---
            patterns = []
            suffixes = [h for h in self.active_honorifics if h in SUFFIX_HONORIFICS]
            if suffixes:
                esc = [re.escape(h) for h in suffixes]
                # Preceded by non-separator (Existing Logic)
                p = r'(?<=[^、。,\s\u3000])(?:' + '|'.join(esc) + r')'
                patterns.append(p)

            romaji = [h for h in self.active_honorifics if h in ROMAJI_HONORIFICS]
            if romaji:
                esc = [re.escape(h) for h in romaji]
                p = r'\b(?:' + '|'.join(esc) + r')\b'
                patterns.append(p)

            standalone = [h for h in self.active_honorifics if h not in SUFFIX_HONORIFICS and h not in ROMAJI_HONORIFICS]
            if standalone:
                esc = [re.escape(h) for h in standalone]
                p = r'(?:' + '|'.join(esc) + r')'
                patterns.append(p)

            if not patterns:
                self.honorifics_pattern = None
            else:
                full_pattern = "|".join(patterns)
                self.honorifics_pattern = re.compile(full_pattern, re.IGNORECASE)

            # --- Build Purple Dot Pattern (Comma Case) ---
            # Looks for "、" (Japanese Comma) followed immediately by ANY active honorific
            all_honors = [re.escape(h) for h in self.active_honorifics]
            if all_honors:
                # Matches: Comma + Honorific (e.g., 、さん)
                p_comma = r'、(?:' + '|'.join(all_honors) + r')'
                self.comma_honorifics_pattern = re.compile(p_comma, re.IGNORECASE)
            else:
                self.comma_honorifics_pattern = None

        # 2. Exceptions Regex
        if not self.exception_phrases:
            self.exceptions_pattern = None
        else:
            sorted_ex = sorted(self.exception_phrases, key=len, reverse=True)
            esc_ex = [re.escape(e) for e in sorted_ex]
            ex_pattern = "|".join(esc_ex)
            self.exceptions_pattern = re.compile(ex_pattern, re.IGNORECASE)

    def open_settings(self):
        win = tk.Toplevel(self)
        win.title("Settings")
        win.geometry("600x600")

        notebook = ttk.Notebook(win)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # TAB 1: General Options
        tab_opts = ttk.Frame(notebook)
        notebook.add(tab_opts, text="General")

        self.var_global_search = tk.BooleanVar(value=self.global_search_enabled)
        ttk.Checkbutton(tab_opts, text="Enable Global Search (Jump to next scenes)", variable=self.var_global_search, bootstyle="round-toggle").pack(anchor="w", padx=20, pady=20)

        # TAB 2: Honorifics
        tab_hono = ttk.Frame(notebook)
        notebook.add(tab_hono, text="Honorifics")

        canvas = tk.Canvas(tab_hono)
        scrollbar = ttk.Scrollbar(tab_hono, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.check_vars = {}
        def add_section(title, items):
            if not items: return
            ttk.Label(scroll_frame, text=title, font=("Consolas", 10, "bold"), bootstyle="primary").pack(anchor="w", padx=10, pady=(15, 5))
            for h in items:
                var = tk.BooleanVar(value=(h in self.active_honorifics))
                self.check_vars[h] = var
                ttk.Checkbutton(scroll_frame, text=h, variable=var).pack(anchor="w", padx=30, pady=2)

        add_section("Strict Suffixes (Must attach to name)", SUFFIX_HONORIFICS)
        add_section("Romaji (Whole word only)", ROMAJI_HONORIFICS)
        add_section("Standalone / Other", STANDALONE_HONORIFICS)
        others = [h for h in self.active_honorifics if h not in DEFAULT_HONORIFICS]
        if others: add_section("Custom / Other", others)

        # TAB 3: Exceptions
        tab_ex = ttk.Frame(notebook)
        notebook.add(tab_ex, text="Exceptions")

        ttk.Label(tab_ex, text="Paste words/phrases to ignore (one per line):").pack(anchor="w", padx=10, pady=5)
        txt_ex = tk.Text(tab_ex, font=FONT_MAIN)
        txt_ex.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        if self.exception_phrases:
            txt_ex.insert("1.0", "\n".join(self.exception_phrases))

        def save_and_close():
            # 1. Honorifics
            new_list = [h for h, var in self.check_vars.items() if var.get()]
            self.active_honorifics = new_list

            # 2. Options
            self.global_search_enabled = self.var_global_search.get()

            # 3. Exceptions
            raw_ex = txt_ex.get("1.0", tk.END)
            self.exception_phrases = [line.strip() for line in raw_ex.splitlines() if line.strip()]

            self.rebuild_regex()
            self.save_config()
            self.apply_blue_dots()
            self.highlight_text_honorifics()
            win.destroy()

        ttk.Button(win, text="Save & Close", command=save_and_close, bootstyle="success").pack(fill=tk.X, pady=10, side=tk.BOTTOM)

    def _get_valid_matches(self, text_content, specific_pattern=None):
        pattern_to_use = specific_pattern if specific_pattern else self.honorifics_pattern
        if not pattern_to_use: return []

        candidates = list(pattern_to_use.finditer(text_content))
        if not candidates: return []

        exceptions = []
        if self.exceptions_pattern:
            exceptions = list(self.exceptions_pattern.finditer(text_content))

        valid_matches = []
        for match in candidates:
            is_exception = False
            m_start, m_end = match.span()
            for ex in exceptions:
                ex_start, ex_end = ex.span()
                if m_start >= ex_start and m_end <= ex_end:
                    is_exception = True
                    break

            if not is_exception:
                valid_matches.append(match)

        return valid_matches

    def toggle_honorifics(self):
        self.apply_blue_dots()
        self.highlight_text_honorifics()

    def jump_next_honorific(self):
        # NOTE: This prioritizes Blue (Normal) honorifics for navigation
        # But we could also add navigation for Purple ones if needed.
        if not self.honorifics_pattern: return

        text_content = self.txt_jp.get("1.0", tk.END)
        start_index = self.txt_jp.index(tk.INSERT)
        cursor_offset = self.txt_jp.count("1.0", start_index, "chars")
        if cursor_offset is None: cursor_offset = (0,)
        cursor_pos = cursor_offset[0]

        matches = self._get_valid_matches(text_content)

        target_match = None
        for m in matches:
            if m.start() > cursor_pos:
                target_match = m
                break

        if target_match:
            self._highlight_and_scroll(target_match)
            return

        if not self.global_search_enabled:
            messagebox.showinfo("End of Scene", "No more valid honorifics in this scene.")
            return

        current_idx = -1
        if self.current_scene_key in self.scene_order:
            current_idx = self.scene_order.index(self.current_scene_key)

        found_scene_key = None
        search_order = self.scene_order[current_idx + 1:] + self.scene_order[:current_idx + 1]

        for key in search_order:
            if key in self.jp_scenes:
                content = self.jp_scenes[key].get_content()
                if self.honorifics_pattern.search(content):
                    v_matches = self._get_valid_matches(content)
                    if v_matches:
                        found_scene_key = key
                        break

        if found_scene_key:
            self.tree.selection_set(found_scene_key)
            self.tree.see(found_scene_key)
            self.load_scene_into_editor(found_scene_key)

            new_text = self.txt_jp.get("1.0", tk.END)
            v_matches = self._get_valid_matches(new_text)
            if v_matches:
                self._highlight_and_scroll(v_matches[0])

    def _highlight_and_scroll(self, match):
        start = f"1.0+{match.start()}c"
        end = f"1.0+{match.end()}c"
        self.txt_jp.tag_remove("active_honorific", "1.0", tk.END)
        self.txt_jp.tag_add("active_honorific", start, end)
        self.txt_jp.mark_set(tk.INSERT, end)
        self.txt_jp.see(start)
        fraction = self.txt_jp.yview()[0]
        self.txt_en.yview_moveto(fraction)
        self.scr_v.set(*self.txt_jp.yview())

    def apply_blue_dots(self):
        if not self.honorifics_pattern:
            for item in self.tree.get_children():
                self.tree.item(item, image='')
            return

        for item_id in self.tree.get_children():
            if item_id in self.jp_scenes:
                content = self.jp_scenes[item_id].get_content()

                # Check 1: Is there a "Comma Edge Case"? (Purple)
                is_purple = False
                if self.comma_honorifics_pattern:
                    if self.comma_honorifics_pattern.search(content):
                         # Ensure valid (not ignored by exception)
                         if self._get_valid_matches(content, self.comma_honorifics_pattern):
                             is_purple = True

                # Check 2: Standard Honorifics (Blue)
                is_blue = False
                if not is_purple: # Only check blue if not purple to save resources, or check both if needed
                    if self.honorifics_pattern.search(content):
                        if self._get_valid_matches(content):
                            is_blue = True

                # Apply Image (Purple takes priority as it is likely an error/edge case)
                if is_purple:
                    self.tree.item(item_id, image=self.purple_dot_img)
                elif is_blue:
                    self.tree.item(item_id, image=self.blue_dot_img)
                else:
                    self.tree.item(item_id, image='')

    def highlight_text_honorifics(self):
        self.txt_jp.tag_remove("honorific", "1.0", tk.END)
        self.txt_jp.tag_remove("honorific_comma", "1.0", tk.END)
        self.txt_jp.tag_remove("active_honorific", "1.0", tk.END)

        text = self.txt_jp.get("1.0", tk.END)

        # 1. Highlight Standard (Blue)
        matches = self._get_valid_matches(text)
        for match in matches:
            start = f"1.0+{match.start()}c"
            end = f"1.0+{match.end()}c"
            self.txt_jp.tag_add("honorific", start, end)

        # 2. Highlight Comma Cases (Purple) - Overlays standard if needed
        if self.comma_honorifics_pattern:
            c_matches = self._get_valid_matches(text, self.comma_honorifics_pattern)
            for match in c_matches:
                start = f"1.0+{match.start()}c"
                end = f"1.0+{match.end()}c"
                self.txt_jp.tag_add("honorific_comma", start, end)

    # --- Alignment & Files ---
    def align_text_content(self, jp_content, en_content):
        def tokenize(text):
            lines = text.splitlines(keepends=True)
            chunks = []
            current_id = None
            current_lines = []
            for line in lines:
                # Use regex that accepts optional semicolon
                match = REGEX_ANCHOR.match(line)
                if match:
                    chunks.append({'id': current_id, 'lines': current_lines})
                    current_id = match.group(1)
                    current_lines = [line]
                else:
                    current_lines.append(line)
            chunks.append({'id': current_id, 'lines': current_lines})
            return chunks

        jp_chunks = tokenize(jp_content)
        en_chunks = tokenize(en_content)

        final_jp = []
        final_en = []
        en_idx = 0

        for j_chunk in jp_chunks:
            j_id = j_chunk['id']
            j_lines = j_chunk['lines']
            e_lines = []
            found_match = False
            temp_idx = en_idx

            if j_id is not None:
                while temp_idx < len(en_chunks):
                    if en_chunks[temp_idx]['id'] == j_id:
                        e_lines = en_chunks[temp_idx]['lines']
                        en_idx = temp_idx + 1
                        found_match = True
                        break
                    temp_idx += 1

            if not found_match and j_id is None and en_idx < len(en_chunks) and en_chunks[en_idx]['id'] is None:
                e_lines = en_chunks[en_idx]['lines']
                en_idx += 1

            max_count = max(len(j_lines), len(e_lines))
            j_padded = list(j_lines)
            if len(j_lines) < max_count: j_padded.extend(['\n'] * (max_count - len(j_lines)))
            e_padded = list(e_lines)
            if len(e_lines) < max_count: e_padded.extend(['\n'] * (max_count - len(e_lines)))

            final_jp.extend(j_padded)
            final_en.extend(e_padded)

        while en_idx < len(en_chunks):
            final_en.extend(en_chunks[en_idx]['lines'])
            en_idx += 1

        return "".join(final_jp), "".join(final_en)

    def parse_file(self, filepath):
        scenes = {}
        order = []
        current_header = "HEADER_METADATA"
        current_block = SceneBlock(current_header)
        scenes[current_header] = current_block
        order.append(current_header)

        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if REGEX_EVENT.match(line):
                    current_header = line.strip()
                    current_block = SceneBlock(current_header)
                    if current_header not in scenes:
                        scenes[current_header] = current_block
                        order.append(current_header)
                    current_block.add_line(line)
                else:
                    current_block.add_line(line)
        return scenes, order

    def load_jp_file(self, path=None):
        if not path: path = filedialog.askopenfilename()
        if not path: return
        try:
            self.jp_scenes, _ = self.parse_file(path)
            self.last_jp_path = path
            self.save_config()
            self.refresh_tree()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def load_en_file(self, path=None):
        if not path: path = filedialog.askopenfilename()
        if not path: return
        try:
            self.en_scenes, self.scene_order = self.parse_file(path)
            self.last_en_path = path
            self.save_config()
            self.refresh_tree()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def on_scene_select(self, event):
        selected = self.tree.selection()
        if not selected: return
        key = selected[0]
        self.load_scene_into_editor(key)

    def load_scene_into_editor(self, key):
        self.save_current_scene_to_memory()
        self.current_scene_key = key

        self.txt_jp.config(state=tk.NORMAL)
        self.txt_jp.delete("1.0", tk.END)
        self.txt_en.delete("1.0", tk.END)

        raw_jp = self.jp_scenes.get(key).get_content() if key in self.jp_scenes else ""
        raw_en = self.en_scenes.get(key).get_content() if key in self.en_scenes else ""

        aligned_jp, aligned_en = self.align_text_content(raw_jp, raw_en)

        self.txt_jp.insert("1.0", aligned_jp)
        self.txt_en.insert("1.0", aligned_en)

        self.txt_jp.config(state=tk.DISABLED)
        self.txt_en.edit_modified(False)
        self.highlight_text_honorifics()

    def save_current_scene_to_memory(self):
        if self.current_scene_key and self.current_scene_key in self.en_scenes:
            text = self.txt_en.get("1.0", "end-1c")
            self.en_scenes[self.current_scene_key].lines = text.splitlines(keepends=True)

    def on_text_modified(self, event):
        if self.txt_en.edit_modified():
            self.unsaved_changes = True
            self.txt_en.edit_modified(False)

    def save_en_file(self):
        self.save_current_scene_to_memory()
        path = filedialog.asksaveasfilename(defaultextension=".txt")
        if not path: return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                for key in self.scene_order:
                    if key in self.en_scenes:
                        for line in self.en_scenes[key].lines:
                            clean_line = REGEX_MSG_COMMENTED.sub(r'\1', line)
                            f.write(clean_line)
                            if not line.endswith('\n'): f.write('\n')
            messagebox.showinfo("Success", "File Saved.")
            self.unsaved_changes = False
            return path
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return None

    def build_ain_file(self):
        if self.unsaved_changes:
             if not messagebox.askyesno("Unsaved Changes", "Save EN file first?"): return
        if not self.last_en_path:
            messagebox.showerror("Error", "No EN file loaded.")
            return
        txt_path = self.save_en_file()
        if not txt_path: return
        ain_path = filedialog.askopenfilename(title="Select Original .ain", filetypes=[("Alice Script", "*.ain")])
        if not ain_path: return
        out_path = filedialog.asksaveasfilename(title="Save New .ain", defaultextension=".ain")
        if not out_path: return

        cmd = []
        if shutil.which("alice"): cmd = ["alice"]
        else: cmd = ["flatpak", "run", "technology.haniwa.alice"]

        cmd.extend(["ain", "edit", "-t", txt_path, "-o", out_path, ain_path])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                messagebox.showinfo("Success", f"Created: {out_path}\n{result.stdout}")
            else:
                messagebox.showerror("Failed", f"Code: {result.returncode}\n{result.stderr}")
        except Exception as e:
             messagebox.showerror("Error", str(e))

    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        keys = self.scene_order if self.scene_order else list(self.jp_scenes.keys())
        for k in keys:
            display = k.replace("; ＥＶ／", "")
            if display == "HEADER_METADATA": display = "[Header / Metadata]"
            status = self.scene_statuses.get(k, '')
            tags = (status,) if status else ()
            self.tree.insert("", "end", iid=k, text=display, tags=tags)
        self.apply_blue_dots()

    def filter_scene_list(self, *args):
        query = self.search_var.get().lower()
        if not query:
            self.refresh_tree()
            return
        self.tree.delete(*self.tree.get_children())
        source_keys = self.scene_order if self.scene_order else list(self.jp_scenes.keys())
        for k in source_keys:
            found = False
            if query in k.lower(): found = True
            if not found and k in self.jp_scenes and query in self.jp_scenes[k].get_content().lower(): found = True
            if not found and k in self.en_scenes and query in self.en_scenes[k].get_content().lower(): found = True

            if found:
                display = k.replace("; ＥＶ／", "")
                status = self.scene_statuses.get(k, '')
                tags = (status,) if status else ()
                self.tree.insert("", "end", iid=k, text=display, tags=tags)
        self.apply_blue_dots()

    def set_scene_status(self, color):
        selected = self.tree.selection()
        if not selected: return
        key = selected[0]
        if color == "none":
            self.tree.item(key, tags=())
            if key in self.scene_statuses: del self.scene_statuses[key]
        else:
            self.tree.item(key, tags=(color,))
            self.scene_statuses[key] = color
        self.save_config()

    def on_close(self):
        self.save_config()
        self.destroy()

    def load_config(self):
        config = configparser.ConfigParser()
        if os.path.exists(CONFIG_FILE):
            config.read(CONFIG_FILE)
            if 'Status' in config:
                self.scene_statuses = dict(config['Status'])
            if 'Paths' in config:
                self.last_jp_path = config['Paths'].get('last_jp', '')
                self.last_en_path = config['Paths'].get('last_en', '')
            if 'Options' in config:
                self.global_search_enabled = config['Options'].getboolean('global_search', False)
                self.win_geometry = config['Options'].get('geometry', '1400x900')
            if 'Honorifics' in config:
                raw_list = config['Honorifics'].get('active', '')
                if raw_list: self.active_honorifics = raw_list.split(',')
                else: self.active_honorifics = []
            if 'Exceptions' in config:
                raw_ex = config['Exceptions'].get('phrases', '')
                if raw_ex:
                    self.exception_phrases = raw_ex.split('|||')
                else:
                    self.exception_phrases = []

    def save_config(self):
        config = configparser.ConfigParser()
        config['Status'] = self.scene_statuses
        config['Paths'] = {
            'last_jp': self.last_jp_path,
            'last_en': self.last_en_path
        }
        config['Options'] = {
            'global_search': str(self.global_search_enabled),
            'geometry': self.geometry()
        }
        config['Honorifics'] = {
            'active': ",".join(self.active_honorifics)
        }
        config['Exceptions'] = {
            'phrases': "|||".join(self.exception_phrases)
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                config.write(f)
        except Exception as e:
            print(f"Error saving config: {e}")

if __name__ == "__main__":
    app = DohnaTool()
    app.mainloop()
