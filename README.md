# Dohna Dohna Unburger Mod

This mod is a comprehensive restoration project for the English release of *Dohna Dohna*.

While it is great to have official localizations, Shiravune unfortunately tends to make decisions that frustrate the core audience—specifically by forcibly removing elements that visual novel fans consider standard. This patch aims to undo those changes, bringing the experience closer to Alicesoft's original vision.

## Key Features

### 1. Honorifics Restored

I have manually restored approximately **98% of all honorifics**.

* This includes restoring terms like *onii-chan*, *onee-sama*, and standard suffixes (-san, -chan, -kun, etc.).
* **Context:** The game script is massive, so this was a significant undertaking. While I may have missed a stray instance here or there, the vast majority are back where they belong.

### 2. Original Japanese Name Order

The name order has been reverted to the original Japanese format (**Surname Firstname**).

* This applies to the main cast and script.
* **Code Modification:** All random NPC generation (Workers and Customers) has been patched to generate names in the correct order.

### 3. Terminology & Re-translation

* **Toratarou’s Nicknames:** In the official loc, many of Toratarou's nicknames were completely made up. I have restored them to the original Japanese phrasing (in Romaji), with the meaning provided in parentheses `()`.
* **General Script:** I have re-translated specific sentences and restored terminology that was localized in a way that didn't make sense for this genre or setting.

---

## Technical Deep Dive

Restoring the name order was the most technically challenging part of this project. It wasn't just a text edit; the game engine generates names for NPCs (employees and customers) at the start of the game and bakes them permanently into the save file.

The Western release also introduces a newline tag (`\n`) in the name generation because the English names wouldn't fit in the UI otherwise.

To fix this, I had to reverse-engineer the game functions responsible for displaying and generating names. I dumped the code and modified the bytecode instructions to swap the order of the strings.

**The Fix:**
I located the relevant functions and swapped the `PUSH` instructions to match the original Japanese logic, while retaining the Western `\n` formatting tag so the UI doesn't break.

Here is the modified bytecode logic:

```assembly
; NameGenerator@GetWorkerName
; RETURN: string
FUNC 29857
    PUSHSTRUCTPAGE
    PUSH 29859              ; Swapped to restore Surname first
    .STRUCTREF NameGenerator m_elem
    CALLMETHOD 1
    S_PUSH "\n"             ; Kept the newline tag for UI spacing
    S_ADD
    PUSHSTRUCTPAGE
    PUSH 29860              ; Swapped to restore Firstname second
    CALLMETHOD 0
    S_ADD
    RETURN
    S_PUSH ""
    RETURN

; NameGenerator@GetCustomerName
; RETURN: string
FUNC 29858
    PUSHSTRUCTPAGE
    PUSH 29866              ; Swapped logic
    CALLMETHOD 0
    S_PUSH "\n"
    S_ADD
    PUSHSTRUCTPAGE
    PUSH 29867              ; Swapped logic
    CALLMETHOD 0
    S_ADD
    RETURN
    S_PUSH ""
    RETURN

```

## Tools Used

This project wouldn't exist without the community and some custom tooling:

1. **Alice-Tools:** This mod relies heavily on the brilliant [alice-tools by nunuhara](https://github.com/nunuhara/alice-tools). It is essential for decompiling and recompiling Alicesoft game files.
2. **Custom Python Translation GUI:** To manage the sheer size of the script, I wrote a custom Python application with a GUI. It parses the text files, displays the original and translated scripts side-by-side, and highlights honorifics in the source text to ensure nothing was missed.

## Closing Notes

This project took a lot of time, but I am proud of the result. I believe this patch makes the reception of the game much more enjoyable for fans who unironically love Japanese pop culture and prefer more authentic experience.
I may push small updates in the future to tweak the script, but the major work—fixing the most glaring issues and the engine-level name generation—is complete.


# Modding Guide

This guide covers setting up the environment using nightly builds, extracting scripts, and using the provided `build.sh` script to reinsert your changes.

## 1. Installation & Environment Setup

To ensure you have the latest features, use the **nightly builds** of Alice Tools, as the standard repository is not up to date.

* **Download:** Get the latest nightly release from the official GitHub: [https://github.com/nunuhara/alice-tools/releases](https://github.com/nunuhara/alice-tools/releases)
* **Install:** Install the Flatpak version downloaded from the releases page.
* **Set up Alias:** Add this to your
`~/.bashrc` to use the `alice` command: `echo "alias alice='flatpak run technology.haniwa.alice'" >> ~/.bashrc`
* **Reload:** Run `source ~/.bashrc` to apply the alias.

---

## 2. Extracting Game Files

You will need the `dohnadohna.ain` and `dohnadohnaEx.ex` files from the game (and optionally from Japanese update 1.01 update if you want to use Dohna-Dohna-Translation-Editor.py).

1. **Extract Main Script (Optional):**
* Command: `alice ain dump -t -o Script.txt dohnadohna.ain`


2. **Extract EX file (UI/Other texts):**
* Command: `alice ex dump -o dohnadohnaEx.txt dohnadohnaEx.ex`


3. (Advanced/optional) **Extract Bytecode :**
* Command: `alice ain dump -c dohnadohna.ain > Functions.txt`



---

## 3. How to Use the Build Script

The `build.sh` script automates the recompilation of your edited files into game-ready formats.

### Folder Preparation

* Create a new folder and copy your original `dohnadohna.ain` into it.
* **Rename the original file** to `dohnadohna-orig.ain`.
* Ensure your translated/edited files are named `Script.txt` and `dohnadohnaEx.txt`.

### Running the Build

Execute the script from your terminal:

```bash
chmod +x build.sh
./build.sh

```

**The script executes the following workflow:**

* **EX Build:** Rebuilds `dohnadohnaEx.ex` using the edited `dohnadohnaEx.txt`.
* **AIN Edit (Pass 1):** Injects your `Script.txt` into the original AIN to create a temporary file.
* **AIN Edit (Pass 2):** Applies bytecode changes from `Functions.txt` to the temporary file to create the final `dohnadohna.ain`.
* **Cleanup:** Creates an `/output` directory, moves the finished `.ain` and `.ex` files there, and removes temporary files.
