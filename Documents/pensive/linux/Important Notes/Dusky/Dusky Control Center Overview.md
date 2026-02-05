# Configuration Bible

> [!INFO] **System Overview**
> 
> **Version:** 2.0 (Forensic Build)
> 
> **Framework:** GTK4 + Libadwaita
> 
> **Language:** Python 3.14+
> 
> **Config Format:** YAML
> 
> **Architecture:** Daemonized Single-Instance with UWSM Compliance.

## 1. The Architecture: Why it feels instant

Before you configure, understand _why_ Dusky works the way it does.

### The "Restaurant" Analogy

Think of Dusky Control Center like a high-end restaurant:

1. **The YAML (`dusky_config.yaml`) is the Menu.** It lists what is available, but it doesn't cook the food.
    
2. **The Python Backend (`rows.py`) is the Kitchen.** It takes the order and prepares the widget.
    
3. **The Daemon Mode.** Unlike most apps that "close" (shut down the kitchen) when you click X, Dusky just turns off the lights. The kitchen staff stays ready. When you open it again, it's instant.
    

### Performance Engineering

> [!NOTE] Under the Hood
> 
> - **Thread Safety:** Every time you see a label update or a toggle switch, a background thread handled the logic so the UI never "stutters."
>     
> - **UWSM Compliance:** Apps launched by Dusky are wrapped in `uwsm-app`. This ensures they know they are in a Hyprland session and don't crash when you close the Control Center.
>     
> - **Hot Reload:** When you save the YAML and hit `Ctrl+R`, Dusky rebuilds the entire restaurant in milliseconds without kicking you out.
>     

## 2. Configuration Structure

The configuration file is located at `$HOME/user_scripts/dusky_config.yaml`.

The hierarchy is strict:

**Pages** $\to$ **Layouts** (Sections) $\to$ **Items** (Widgets)

```
pages:
  - id: unique_page_id
    title: "Page Title"
    icon: icon-name-symbolic
    layout:
      - type: section
        properties: { ... }
        items: [ ... ]
```

## 3. Widget Reference

This section details every component available in the widget factory (`rows.py`).

### 3.1 Standard Button (`button`)

The workhorse of the UI. Used for launching apps or scripts.

**Event Type:** `on_press`

- `type`: Must be `exec` (run command) or `redirect` (change page).
    
- `terminal`: If `true`, opens a Kitty window holding the process.
    

```
- type: button
  properties:
    title: System Update
    description: Run the Arch updater
    icon: system-software-update-symbolic
    style: suggested  # Options: default, suggested, destructive
    button_text: "Run"
  on_press:
    type: exec
    command: kitty --hold sh -c "paru -Syu"
    terminal: false
```

### 3.2 Toggle Switch (`toggle`)

A complex widget that must **read** state (is it on?) and **write** state (turn it on).

> [!TIP] The "State Monitor"
> 
> Toggles use a `StateMonitorMixin`. They poll the system every few seconds to see if the switch should be ON or OFF.

**Properties:**

- `state_command`: A shell command. If it returns "enabled", "on", or "active", the switch turns green.
    
- `key`: Alternatively, link to a file in `~/.config/dusky/settings/`.
    
- `interval`: How often (in seconds) to check the state.
    

**Event Type:** `on_toggle`

- Requires `enabled` and `disabled` blocks.
    

```
- type: toggle
  properties:
    title: Wi-Fi
    icon: network-wireless-symbolic
    state_command: nmcli radio wifi
    interval: 5
  on_toggle:
    enabled:
      type: exec
      command: nmcli radio wifi on
    disabled:
      type: exec
      command: nmcli radio wifi off
```

### 3.3 Slider (`slider`)

Used for Volume, Brightness, or custom integer values.

**Properties:**

- `min`, `max`, `step`: Define the range.
    
- `debounce`: If `true`, waits for you to stop dragging before running the command (prevents lag).
    

**Event Type:** `on_change`

- The `command` string supports a `{value}` placeholder which is replaced by the number.
    

```
- type: slider
  properties:
    title: Brightness
    icon: display-brightness-symbolic
    min: 0
    max: 100
    step: 5
    debounce: true
  on_change:
    type: exec
    command: brightnessctl set {value}%
```

### 3.4 Selection Dropdown (`selection`)

A dropdown menu (`Adw.ComboRow`) for choosing between pre-defined options.

**Properties:**

- `options`: A list of strings to display.
    

**Event Type:** `on_change`

- The `command` string supports a `{value}` placeholder (the text selected).
    

```
- type: selection
  properties:
    title: Power Profile
    icon: battery-level-80-symbolic
    options:
      - Performance
      - Balanced
      - Power Saver
  on_change:
    type: exec
    command: powerprofilesctl set {value}
```

### 3.5 Text Entry (`entry`)

A text box with an "Apply" button.

**Event Type:** `on_action`

- The `command` string supports a `{value}` placeholder (the text typed).
    

```
- type: entry
  properties:
    title: Set Hostname
    icon: network-server-symbolic
    button_text: "Apply"
  on_action:
    type: exec
    command: hostnamectl set-hostname {value}
    terminal: true
```

### 3.6 Grid Cards (`grid_card` / `toggle_card`)

Large, square buttons used in the `grid_section` layout. Ideal for the "Home" page.

- `grid_card`: Acts like a Button.
    
- `toggle_card`: Acts like a Toggle (changes color when active).
    

```
- type: toggle_card
  properties:
    title: Dark Mode
    icon: weather-clear-night-symbolic
    key: dusky_theme/state # Saves state to file
  on_toggle:
    enabled:
      type: exec
      command: theme_ctl.sh set dark
    disabled:
      type: exec
      command: theme_ctl.sh set light
```

### 3.7 Dynamic Label (`label`)

Displays text that updates automatically.

**Value Types:**

- `exec`: Runs a command (e.g., `free -h`).
    
- `file`: Reads a file path.
    
- `system`: Reads internal cached values (`kernel_version`, `cpu_model`, `memory_total`).
    

```
- type: label
  properties:
    title: Kernel
    interval: 60 # Updates every minute
  value:
    type: system
    key: kernel_version
```

### 3.8 Expander Row (`expander`)

A row that unfolds to reveal children. Useful for cleaning up cluttered pages.

```
- type: expander
  properties:
    title: Advanced Network Settings
    icon: preferences-system-network-symbolic
  items:
    - type: button
      properties: { title: "DNS Settings", ... }
    - type: toggle
      properties: { title: "IPv6", ... }
```

### 3.9 Warning Banner (`warning_banner`)

A static, styled widget used to display alerts.

```
- type: warning_banner
  properties:
    title: "Read Only"
    message: "These are system defaults. Do not edit directly."
```

## 4. Advanced Features

### 4.1 Hot Reload (`Ctrl+R`)

You do **not** need to restart the application to see changes.

1. Edit `dusky_config.yaml`.
    
2. Focus the Dusky window.
    
3. Press `Ctrl + R`.
    

> [!WARNING] State Preservation
> 
> Dusky attempts to remember which page you were on. If you delete that page in the config, it will default back to the first page.

### 4.2 Deep Search (`Ctrl+F`)

Dusky includes a recursive indexing engine.

- It indexes Page Titles, Section Titles, Item Titles, and Descriptions.
    
- It creates "Breadcrumbs" (e.g., _Home > Network > VPN_) so you know exactly where a setting lives.
    
- **Grid Cards** and **Toggles** found in search results are automatically converted into List Rows for better readability in the search view.
    

### 4.3 Sidebar Toggle

The interface uses `Adw.OverlaySplitView`.

- On wide monitors, the sidebar is pinned.
    
- On small windows, the sidebar collapses.
    
- Clicking the "Dusky" icon in the top left or the sidebar toggle button will slide the menu in/out.
    

## 5. Troubleshooting & Debugging

### "The toggle switches back instantly"

This happens when the `state_command` reports the old state.

- **Cause:** You clicked the toggle, the command ran, but the system (e.g., NetworkManager) took 1 second to actually change status. The Monitor checked instantly, saw the old status, and flipped the switch back.
    
- **Fix:** Ensure your toggle scripts wait for the process to finish, or accept that the switch will correct itself on the next `interval` tick.
    

### "My command works in terminal but not in Dusky"

- **Cause:** Path issues.
    
- **Fix:** Always use absolute paths (e.g., `/usr/bin/htop` instead of `htop`). While Dusky handles `$HOME` expansion, it does not load your `.bashrc` aliases unless you explicitly call `bash -i -c "command"`.
    

### "The app won't open"

- **Check:** Run `dusky_control_center.py` from a terminal to see the stderr output.
    
- **Recover:** If the config is broken, Dusky will launch into a special "Error State" page showing you the Python stack trace, allowing you to fix the YAML and Hot Reload without crashing.**ROLE:** You are a Senior Technical Technical Writer and Systems Architect specializing in Linux GUI development, GTK4/Libadwaita, and Python optimization. You have a talent for explaining complex backend architectures to end-users using clear analogies, while maintaining technical accuracy for power users.
    
    **CONTEXT:** I am deploying a custom-built GTK4 Control Center app ("Dusky Control Center") to over 700,000 users on Arch Linux/Hyprland. The app is built with Python (using `PyGObject`), configured via YAML, and styled via CSS. It features hot-reloading, UWSM (Universal Wayland Session Manager) compliance, thread-safe execution, and a modular widget system.
    
    **TASK PHASE 1: FORENSIC ANALYSIS** Before writing a single word of the tutorial, you must perform a forensic analysis of the provided codebases. Do not output this analysis, but hold it in your context to inform the documentation.
    
    1. **Analyze `dusky_control_center.py`:** Understand the Application Lifecycle, the Daemon/Single-Instance logic, the Hot-Reload mechanism (async threading), the Search architecture (recursive indexing), and the UI construction (OverlaySplitView).
        
    2. **Analyze `rows.py`:** Deconstruct the Widget Factory. Identify every single supported `ItemType` (Button, Toggle, Slider, Selection, Entry, Grid Card, etc.). Understand the specific optimizations like "Fast Path" execution for Sliders (subprocess.Popen vs utility.execute_command) and Debouncing logic.
        
    3. **Analyze `utility.py`:** Understand the thread-safe caching (`_ComputeOnceCache`), atomic file I/O for settings, and the `uwsm-app` command wrapping for process detachment.
        
    4. **Analyze `dusky_config.yaml`:** Understand the schema: Pages -> Sections -> Items.
        
    5. **Analyze `dusky_style.css`:** Understand the "Boxed List" grouping logic (CSS pseudo-classes) and Libadwaita design tokens.
        
    
    **TASK PHASE 2: THE OUTPUT** Write a comprehensive, future-proof **Obsidian-Formatted Markdown Configuration Guide**. This document will serve as the "Bible" for this application. It must be beautiful, categorized, and easy to read.
    
    **REQUIREMENTS:**
    
    6. **Obsidian Formatting:** Use Callouts (`> [!INFO]`, `> [!WARNING]`), Code Blocks with language highlighting, Headers, and bolding for emphasis.
        
    7. **Analogies:** Use real-world analogies to explain how the YAML config talks to the Python backend (e.g., "The YAML is the menu, the Python is the kitchen").
        
    8. **Comprehensive Configuration Guide:**
        
        - Walk through **every single widget type** found in `rows.py` (`button`, `toggle`, `slider`, `selection`, `entry`, `grid_card`, `toggle_card`, `label`, `navigation`, `expander`).
            
        - For each widget, provide a YAML snippet example and explain its properties (`debounce`, `terminal`, `command`, `options`, `placeholder`, etc.).
            
        - Explain the difference between `on_press`, `on_change`, and `on_toggle`.
            
    9. **Feature Deep Dives:**
        
        - Explain **Hot Reload** (Ctrl+R) and why it's safe (state preservation).
            
        - Explain **Search** (Ctrl+F) and how it finds items deeply nested in menus.
            
        - Explain the **Sidebar Toggle** logic.
            
    10. **Performance & Architecture (Simplified):** Briefly explain _why_ this app is fast (Thread pooling, Slider fast-paths, UWSM compliance) so the user appreciates the engineering.
        
    
    **TONE:** Professional, authoritative, yet extremely accessible. Assume the user is smart but may be new to coding.
    
    **INPUT FILES:** [Paste the contents of `dusky_control_center.py`, `rows.py`, `utility.py`, `dusky_config.yaml`, and `dusky_style.css` here]