import evdev

print(f"{'NAME':<40} | {'PHYS':<20} | {'CAPABILITIES'}")
print("-" * 100)

for path in evdev.list_devices():
    dev = evdev.InputDevice(path)
    
    # Get the capabilities (returns a dict)
    caps = dev.capabilities()
    
    # Check for specific event types
    # 1 = EV_KEY (Keys/Buttons)
    # 3 = EV_ABS (Absolute Axis - Touchpads/Tablets use this)
    has_keys = 1 in caps
    has_abs = 3 in caps
    
    # Check for Input Properties (INPUT_PROP_POINTER, etc)
    # This is often hidden in a deeper property list
    props = dev.input_props()
    is_pointer = 0 in props # 0 is usually INPUT_PROP_POINTER
    
    # Color code for visibility
    # RED if it has Keys but NO Abs (Likely a Keyboard)
    # YELLOW if it has Keys AND Abs (Likely a Trackpad)
    color = "\033[1;32m" # Green (Generic)
    type_guess = "UNKNOWN"
    
    if has_keys and not has_abs:
        color = "\033[1;31m" # Red
        type_guess = "KEYBOARD"
    elif has_keys and has_abs:
        color = "\033[1;33m" # Yellow
        type_guess = "TRACKPAD/TABLET"
        
    print(f"{color}{dev.name:<40}\033[0m | {dev.phys:<20} | {type_guess} (Has EV_ABS: {has_abs})")
